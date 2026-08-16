"""Helper for importing custom IR protocol modules and SmartIR code sets.

Update-safe locations (survive HACS updates, recommended):
    <config>/transcold_ir/protocols/*.py   - custom protocol classes
    <config>/transcold_ir/codes/*.json     - SmartIR climate code sets

Legacy location (wiped on every HACS update, still scanned):
    <config>/custom_components/transcold_ir_climate/protocols/*.py

A custom protocol must:
1. Inherit from BaseIRProtocol
2. Set class attributes: name, description, supported_models
3. Implement encode() and get_raw_timings() methods
4. Be importable as a Python module

Example custom protocol file: my_ac.py
--------------------------------------
from custom_components.transcold_ir_climate.protocols.base import BaseIRProtocol

class MyACProtocol(BaseIRProtocol):
    name = "my_ac"
    description = "My Custom AC"
    supported_models = ["MyAC Model X"]

    def encode(self, mode, temp, fan, power=True, swing=False, command_format="raw"):
        ...

    def get_raw_timings(self, state):
        return self.encode(**state, command_format="raw")
--------------------------------------
"""

import importlib.util
import logging
from pathlib import Path

from homeassistant.core import HomeAssistant

from ..const import CODES_SUBDIR, CUSTOM_PROTOCOLS_SUBDIR, DATA_DIR
from . import BUILTIN_PROTOCOLS, PROTOCOLS, register_protocol, unregister_protocol
from .base import BaseIRProtocol
from .smartir_codeset import SmartIRCodesetError, make_codeset_protocol

_LOGGER = logging.getLogger(__name__)


def get_data_dir(hass: HomeAssistant) -> Path:
    """Return the update-safe data directory, creating it if needed."""
    base = Path(hass.config.path(DATA_DIR))
    (base / CODES_SUBDIR).mkdir(parents=True, exist_ok=True)
    (base / CUSTOM_PROTOCOLS_SUBDIR).mkdir(parents=True, exist_ok=True)
    return base


def _load_protocol_module(file_path: Path) -> set[str]:
    """Import one .py file and register the protocol classes it defines.

    Returns the names it registered.
    """
    module_name = file_path.stem
    spec = importlib.util.spec_from_file_location(
        f"custom_components.transcold_ir_climate.protocols.{module_name}",
        file_path,
    )
    if spec is None or spec.loader is None:
        return set()

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    registered: set[str] = set()
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseIRProtocol)
            and attr is not BaseIRProtocol
            and getattr(attr, "name", None)
            and attr.name not in BUILTIN_PROTOCOLS
        ):
            # Remember the origin so a deleted file can be reconciled away
            attr.source_file = file_path.name
            register_protocol(attr.name, attr)
            registered.add(attr.name)
            _LOGGER.info(
                "Registered custom IR protocol: %s (%s)",
                attr.name,
                getattr(attr, "description", "No description"),
            )
    return registered


def discover_custom_protocols(hass: HomeAssistant) -> None:
    """Discover custom protocols and SmartIR code sets. Blocking - run in executor.

    Reconciles the registry with what is on disk, so protocols whose file was
    deleted disappear without needing a restart.
    """
    skip = ("__init__", "base", "import_helper", "transcold", "smartir_codeset")

    # Legacy location inside the integration + update-safe location
    legacy = Path(
        hass.config.path("custom_components", "transcold_ir_climate", "protocols")
    )
    data_dir = get_data_dir(hass)
    protocol_dirs = [legacy, data_dir / CUSTOM_PROTOCOLS_SUBDIR]

    found: set[str] = set()
    for base_path in protocol_dirs:
        if not base_path.exists():
            continue
        for file_path in sorted(base_path.glob("*.py")):
            if file_path.stem in skip:
                continue
            try:
                found |= _load_protocol_module(file_path)
            except Exception as err:
                _LOGGER.warning(
                    "Failed to load custom protocol %s: %s", file_path.name, err
                )

    # Drop Python protocols whose source file is gone
    for name in [
        n
        for n, cls in PROTOCOLS.items()
        if n not in BUILTIN_PROTOCOLS
        and not n.startswith("smartir_")
        and getattr(cls, "source_file", None)
    ]:
        if name not in found:
            unregister_protocol(name)

    discover_codesets(hass)


def discover_codesets(hass: HomeAssistant) -> None:
    """(Re)register all SmartIR code sets. Blocking - run in executor."""
    codes_dir = get_data_dir(hass) / CODES_SUBDIR

    found: set[str] = set()
    for file_path in sorted(codes_dir.glob("*.json")):
        try:
            protocol_class = make_codeset_protocol(file_path)
        except (SmartIRCodesetError, ValueError, OSError) as err:
            _LOGGER.warning(
                "Skipping SmartIR code set %s: %s", file_path.name, err
            )
            continue
        register_protocol(protocol_class.name, protocol_class)
        found.add(protocol_class.name)
        _LOGGER.debug(
            "Registered SmartIR code set: %s (%s)",
            protocol_class.name,
            protocol_class.description,
        )

    # Drop registrations whose file disappeared
    for name in [n for n in PROTOCOLS if n.startswith("smartir_")]:
        if name not in found:
            unregister_protocol(name)


def get_protocol_info() -> dict:
    """Get info about all registered protocols."""
    info = {}
    for name, protocol_class in PROTOCOLS.items():
        proto = protocol_class()
        info[name] = {
            "name": proto.name,
            "description": proto.description,
            "supported_models": proto.supported_models,
            "min_temp": proto.min_temp,
            "max_temp": proto.max_temp,
            "supports_swing": proto.supports_swing,
            "hvac_modes": proto.hvac_modes,
            "fan_modes": proto.fan_modes,
            "builtin": name in BUILTIN_PROTOCOLS,
            "source": getattr(proto, "source_file", None),
        }
    return info
