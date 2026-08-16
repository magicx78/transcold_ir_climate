"""Helper for importing custom IR protocol modules.

Users can place custom protocol files in:
<config>/custom_components/transcold_ir_climate/protocols/

A custom protocol must:
1. Inherit from BaseIRProtocol
2. Set class attributes: name, description, supported_models
3. Implement encode() and get_raw_timings() methods
4. Be importable as a Python module

Example custom protocol file: my_ac.py
--------------------------------------
from .base import BaseIRProtocol

class MyACProtocol(BaseIRProtocol):
    name = "my_ac"
    description = "My Custom AC"
    supported_models = ["MyAC Model X"]
    min_temp = 16
    max_temp = 30
    supports_swing = True
    hvac_modes = ["off", "cool", "heat", "dry", "fan_only", "auto"]
    fan_modes = ["auto", "low", "medium", "high"]

    def encode(self, mode, temp, fan, power=True, swing=False, command_format="raw"):
        # Your encoding logic here
        if command_format == "raw":
            return [9000, -4500, ...]  # raw timings
        return "base64_or_other_format"

    def get_raw_timings(self, state):
        return self.encode(**state, command_format="raw")
--------------------------------------
"""

import importlib
import logging
import os
from pathlib import Path

from homeassistant.core import HomeAssistant

from . import PROTOCOLS, register_protocol
from .base import BaseIRProtocol

_LOGGER = logging.getLogger(__name__)


def discover_custom_protocols(hass: HomeAssistant) -> None:
    """Discover and register custom protocol modules from the protocols directory."""
    try:
        # Path to custom protocols
        base_path = Path(hass.config.path("custom_components", "transcold_ir_climate", "protocols"))
        if not base_path.exists():
            return

        for file_path in base_path.glob("*.py"):
            module_name = file_path.stem
            if module_name in ("__init__", "base", "import_helper", "transcold"):
                continue

            try:
                # Dynamic import
                spec = importlib.util.spec_from_file_location(
                    f"custom_components.transcold_ir_climate.protocols.{module_name}",
                    file_path,
                )
                if spec is None or spec.loader is None:
                    continue

                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find protocol classes
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (
                        isinstance(attr, type)
                        and issubclass(attr, BaseIRProtocol)
                        and attr is not BaseIRProtocol
                        and hasattr(attr, "name")
                        and attr.name
                    ):
                        if attr.name not in PROTOCOLS:
                            register_protocol(attr.name, attr)
                            _LOGGER.info(
                                "Registered custom IR protocol: %s (%s)",
                                attr.name,
                                getattr(attr, "description", "No description"),
                            )

            except Exception as err:
                _LOGGER.warning("Failed to load custom protocol %s: %s", module_name, err)

    except Exception as err:
        _LOGGER.error("Error discovering custom protocols: %s", err)


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
        }
    return info
