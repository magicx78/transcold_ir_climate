"""SmartIR code-set support.

Loads SmartIR climate JSON files (https://github.com/smartHomeHub/SmartIR)
and exposes each file as an IR protocol. Instead of computing the IR frame,
the protocol looks up the pre-recorded command for (mode, fan, temp).

Supported files: "supportedController": "Broadlink" with
"commandsEncoding": "Base64". The Base64 commands can additionally be
decoded back into raw timings so ESPHome transmitters work too.
"""

from __future__ import annotations

import base64
import json
import struct
from pathlib import Path

from .base import BaseIRProtocol

# SmartIR pulse unit: 2^-15 s. Canonical conversion factor 269/8192.
_US_PER_UNIT = 8192 / 269

# SmartIR mode/fan vocabularies differ slightly per file; map to the
# BaseIRProtocol vocabulary (off/cool/heat/dry/fan_only/auto and
# auto/low/medium/high).
_MODE_TO_PROTOCOL = {
    "cool": "cool",
    "heat": "heat",
    "dry": "dry",
    "fan": "fan_only",
    "fan_only": "fan_only",
    "auto": "auto",
    "heat_cool": "auto",
}

_FAN_TO_PROTOCOL = {
    "auto": "auto",
    "low": "low",
    "min": "low",
    "level1": "low",
    "mid": "medium",
    "medium": "medium",
    "med": "medium",
    "level2": "medium",
    "high": "high",
    "max": "high",
    "level3": "high",
}


def broadlink_b64_to_raw(b64_command: str) -> list[int]:
    """Decode a Broadlink Base64 IR packet into raw timings (us).

    Returns alternating positive (mark) / negative (space) microsecond
    values, the same convention encode_to_raw_timings() uses.
    """
    if b64_command.startswith("b64:"):
        b64_command = b64_command[4:]
    packet = base64.b64decode(b64_command)
    if len(packet) < 4 or packet[0] != 0x26:
        raise ValueError("Not a Broadlink IR packet (must start with 0x26)")

    (length,) = struct.unpack("<H", packet[2:4])
    data = packet[4 : 4 + length]

    timings: list[int] = []
    i = 0
    mark = True
    while i < len(data):
        units = data[i]
        i += 1
        if units == 0x00:
            if i + 2 > len(data):
                break
            (units,) = struct.unpack(">H", data[i : i + 2])
            i += 2
        us = max(1, round(units * _US_PER_UNIT))
        timings.append(us if mark else -us)
        mark = not mark
    return timings


class SmartIRCodesetError(ValueError):
    """Raised when a SmartIR JSON file cannot be used."""


def validate_smartir_climate(data: dict) -> dict:
    """Validate a SmartIR climate JSON dict; return summary info.

    Raises SmartIRCodesetError with a human-readable reason when the file
    cannot be used by this integration.
    """
    if not isinstance(data, dict):
        raise SmartIRCodesetError("JSON root must be an object")

    controller = str(data.get("supportedController", "")).lower()
    encoding = str(data.get("commandsEncoding", "")).lower()
    if controller != "broadlink":
        raise SmartIRCodesetError(
            f"Unsupported controller '{data.get('supportedController')}' "
            "(only Broadlink code sets are supported)"
        )
    if encoding != "base64":
        raise SmartIRCodesetError(
            f"Unsupported commandsEncoding '{data.get('commandsEncoding')}' "
            "(only Base64 is supported)"
        )

    commands = data.get("commands")
    if not isinstance(commands, dict) or not commands:
        raise SmartIRCodesetError("Missing 'commands' object")

    modes = [m for m in data.get("operationModes", []) if m in _MODE_TO_PROTOCOL]
    if not modes:
        raise SmartIRCodesetError(
            f"No usable operationModes in {data.get('operationModes')}"
        )

    return {
        "manufacturer": data.get("manufacturer", "Unknown"),
        "models": data.get("supportedModels", []),
        "min_temp": int(data.get("minTemperature", 16)),
        "max_temp": int(data.get("maxTemperature", 30)),
        "operation_modes": modes,
        "fan_modes": data.get("fanModes", []),
        "has_off": "off" in commands,
    }


class SmartIRCodesetProtocol(BaseIRProtocol):
    """A protocol backed by a SmartIR climate code-set file.

    Subclasses are generated per JSON file by make_codeset_protocol().
    """

    codeset: dict = {}
    # protocol vocabulary -> key used inside the codeset's commands dict
    mode_keys: dict[str, str] = {}
    fan_keys: dict[str, str] = {}
    source_file: str = ""

    def _lookup(self, mode: str, temp: int, fan: str) -> str:
        commands = self.codeset["commands"]

        if mode not in self.mode_keys:
            mode = next(iter(self.mode_keys))
        node = commands[self.mode_keys[mode]]
        if isinstance(node, str):
            return node

        # Optional fan layer
        fan_key = self.fan_keys.get(fan)
        if fan_key and fan_key in node:
            node = node[fan_key]
        elif any(k in node for k in self.fan_keys.values()):
            node = node[next(k for k in self.fan_keys.values() if k in node)]
        if isinstance(node, str):
            return node

        # Optional swing layer (pick a stable default), then temperature
        for _ in range(2):
            keys = list(node.keys())
            temp_keys = [k for k in keys if _is_int(k)]
            if temp_keys:
                target = min(
                    temp_keys, key=lambda k: abs(int(k) - int(temp))
                )
                node = node[target]
            else:
                node = node[keys[0]]
            if isinstance(node, str):
                return node

        raise SmartIRCodesetError(
            f"No command found for mode={mode}, temp={temp}, fan={fan} "
            f"in {self.source_file}"
        )

    def encode(
        self,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
        command_format: str = "broadlink",
    ):
        """Return the pre-recorded command for the requested state."""
        if not power:
            command = self.codeset["commands"].get("off")
            if not isinstance(command, str):
                raise SmartIRCodesetError(
                    f"Code set {self.source_file} has no 'off' command"
                )
        else:
            command = self._lookup(mode, temp, fan)

        if command_format == "broadlink":
            return command
        # Raw timings (e.g. for ESPHome transmitters)
        return broadlink_b64_to_raw(command)

    def get_raw_timings(self, state: dict) -> list:
        """Get raw IR timings from state dict."""
        return self.encode(
            mode=state.get("mode", self.default_mode),
            temp=state.get("temp", self.default_temp),
            fan=state.get("fan", self.default_fan),
            power=state.get("power", True),
            swing=state.get("swing", False),
            command_format="raw",
        )


def _is_int(value: str) -> bool:
    try:
        int(value)
    except (TypeError, ValueError):
        return False
    return True


def make_codeset_protocol(path: Path) -> type[SmartIRCodesetProtocol]:
    """Build a protocol class from a SmartIR climate JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    info = validate_smartir_climate(data)

    mode_keys = {
        _MODE_TO_PROTOCOL[m]: m
        for m in info["operation_modes"]
    }
    fan_keys = {
        _FAN_TO_PROTOCOL[f]: f
        for f in info["fan_modes"]
        if f in _FAN_TO_PROTOCOL
    }
    if not fan_keys:
        fan_keys = {"auto": "auto"}

    models = ", ".join(info["models"]) if info["models"] else path.stem

    attrs = {
        "name": f"smartir_{path.stem}",
        "description": f"{info['manufacturer']} ({models})",
        "supported_models": info["models"],
        "min_temp": info["min_temp"],
        "max_temp": info["max_temp"],
        "default_temp": min(max(22, info["min_temp"]), info["max_temp"]),
        "hvac_modes": ["off"] + sorted(mode_keys.keys()),
        "fan_modes": list(fan_keys.keys()),
        "supports_swing": False,
        "codeset": data,
        "mode_keys": mode_keys,
        "fan_keys": fan_keys,
        "source_file": path.name,
    }
    return type(f"SmartIR_{path.stem}", (SmartIRCodesetProtocol,), attrs)
