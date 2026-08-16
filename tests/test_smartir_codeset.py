"""Tests for the SmartIR code-set protocol support.

Runs standalone (no Home Assistant required):

    python tests/test_smartir_codeset.py

or via pytest.
"""

import json
import sys
import tempfile
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parent.parent / (
    "custom_components/transcold_ir_climate"
)

# The protocols package has no Home Assistant dependencies, so it can be
# imported directly (import_helper.py, which does, is never imported here).
sys.path.insert(0, str(COMPONENT_DIR))
from protocols.smartir_codeset import (  # noqa: E402
    SmartIRCodesetError,
    broadlink_b64_to_raw,
    make_codeset_protocol,
    validate_smartir_climate,
)
from protocols.transcold import TranscoldProtocol  # noqa: E402


# --- Fixtures --------------------------------------------------------------

# Real Broadlink payloads, produced by the (independently tested) Transcold
# encoder, so the decoder is checked against known-good data.
_TC = TranscoldProtocol()
B64_COOL_22 = _TC.encode(mode="cool", temp=22, fan="auto", command_format="broadlink")
B64_OFF = _TC.encode(
    mode="cool", temp=22, fan="auto", power=False, command_format="broadlink"
)

CODESET = {
    "manufacturer": "TestCorp",
    "supportedModels": ["TC-100"],
    "supportedController": "Broadlink",
    "commandsEncoding": "Base64",
    "minTemperature": 18,
    "maxTemperature": 24,
    "operationModes": ["cool", "heat"],
    "fanModes": ["auto", "high"],
    "commands": {
        "off": B64_OFF,
        "cool": {
            "auto": {str(t): B64_COOL_22 for t in range(18, 25)},
            "high": {str(t): B64_COOL_22 for t in range(18, 25)},
        },
        "heat": {
            "auto": {str(t): B64_COOL_22 for t in range(18, 25)},
            "high": {str(t): B64_COOL_22 for t in range(18, 25)},
        },
    },
}


def _write_codeset(tmpdir, data, stem="testcorp_ac"):
    path = Path(tmpdir) / f"{stem}.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


# --- Broadlink decoder -----------------------------------------------------


def test_b64_decode_is_inverse_of_encode():
    """Decoding a Broadlink payload must reproduce the original timings."""
    original = _TC.encode_to_raw_timings(TranscoldProtocol.KNOWN_GOOD_STATE)
    decoded = broadlink_b64_to_raw(
        _TC.encode_to_broadlink(TranscoldProtocol.KNOWN_GOOD_STATE)
    )

    assert len(decoded) == len(original), (
        f"timing count differs: {len(decoded)} != {len(original)}"
    )
    for i, (dec, orig) in enumerate(zip(decoded, original)):
        assert (dec < 0) == (orig < 0), f"mark/space flipped at index {i}"
        # One Broadlink unit is ~30.5 us, so quantisation error stays below it.
        assert abs(abs(dec) - abs(orig)) <= 31, (
            f"timing {i} drifted: {dec} vs {orig}"
        )


def test_b64_decode_accepts_prefixed_payload():
    """The 'b64:' prefix used on the wire is stripped before decoding."""
    assert broadlink_b64_to_raw(f"b64:{B64_COOL_22}") == broadlink_b64_to_raw(
        B64_COOL_22
    )


def test_b64_decode_rejects_non_ir_packet():
    """RF packets (0xb2) and garbage must not be silently accepted."""
    import base64

    rf_packet = base64.b64encode(bytes([0xB2, 0x00, 0x04, 0x00, 1, 2, 3, 4]))
    try:
        broadlink_b64_to_raw(rf_packet.decode())
    except ValueError:
        return
    raise AssertionError("expected ValueError for non-IR packet")


# --- Code-set validation ---------------------------------------------------


def test_validate_accepts_broadlink_base64():
    info = validate_smartir_climate(CODESET)
    assert info["manufacturer"] == "TestCorp"
    assert info["min_temp"] == 18
    assert info["max_temp"] == 24
    assert info["operation_modes"] == ["cool", "heat"]
    assert info["has_off"] is True


def test_validate_rejects_foreign_controller():
    data = dict(CODESET, supportedController="MQTT")
    try:
        validate_smartir_climate(data)
    except SmartIRCodesetError as err:
        assert "MQTT" in str(err)
        return
    raise AssertionError("expected SmartIRCodesetError for non-Broadlink set")


def test_validate_rejects_hex_encoding():
    data = dict(CODESET, commandsEncoding="Hex")
    try:
        validate_smartir_climate(data)
    except SmartIRCodesetError:
        return
    raise AssertionError("expected SmartIRCodesetError for non-Base64 set")


def test_validate_rejects_missing_commands():
    data = {k: v for k, v in CODESET.items() if k != "commands"}
    try:
        validate_smartir_climate(data)
    except SmartIRCodesetError:
        return
    raise AssertionError("expected SmartIRCodesetError without commands")


# --- Generated protocol class ----------------------------------------------


def test_protocol_class_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        cls = make_codeset_protocol(_write_codeset(tmp, CODESET))

    assert cls.name == "smartir_testcorp_ac"
    assert "TestCorp" in cls.description and "TC-100" in cls.description
    assert cls.min_temp == 18 and cls.max_temp == 24
    assert cls.hvac_modes == ["off", "cool", "heat"]
    assert set(cls.fan_modes) == {"auto", "high"}


def test_protocol_lookup_returns_recorded_command():
    with tempfile.TemporaryDirectory() as tmp:
        proto = make_codeset_protocol(_write_codeset(tmp, CODESET))()

    assert proto.encode(mode="cool", temp=22, fan="auto") == B64_COOL_22
    assert proto.encode(mode="heat", temp=18, fan="high") == B64_COOL_22


def test_protocol_power_off_uses_off_command():
    with tempfile.TemporaryDirectory() as tmp:
        proto = make_codeset_protocol(_write_codeset(tmp, CODESET))()

    assert proto.encode(mode="cool", temp=22, fan="auto", power=False) == B64_OFF


def test_protocol_clamps_unknown_temperature_to_nearest():
    """A temperature outside the recorded range picks the closest entry."""
    with tempfile.TemporaryDirectory() as tmp:
        proto = make_codeset_protocol(_write_codeset(tmp, CODESET))()

    # 30 C is not recorded (max is 24) - must not raise
    assert proto.encode(mode="cool", temp=30, fan="auto") == B64_COOL_22


def test_protocol_raw_format_returns_timings():
    """ESPHome targets ask for raw timings; the b64 command is decoded."""
    with tempfile.TemporaryDirectory() as tmp:
        proto = make_codeset_protocol(_write_codeset(tmp, CODESET))()

    timings = proto.encode(
        mode="cool", temp=22, fan="auto", command_format="raw"
    )
    assert isinstance(timings, list)
    assert len(timings) > 10
    assert timings[0] > 0 and timings[1] < 0  # starts with mark, then space
    assert timings == proto.get_raw_timings({"mode": "cool", "temp": 22, "fan": "auto"})


def test_protocol_without_fan_layer():
    """Code sets that skip the fan level (mode -> temp) still resolve."""
    flat = dict(CODESET)
    flat["commands"] = {
        "off": B64_OFF,
        "cool": {str(t): B64_COOL_22 for t in range(18, 25)},
        "heat": {str(t): B64_COOL_22 for t in range(18, 25)},
    }
    with tempfile.TemporaryDirectory() as tmp:
        proto = make_codeset_protocol(_write_codeset(tmp, flat))()

    assert proto.encode(mode="cool", temp=20, fan="auto") == B64_COOL_22


def test_protocol_maps_smartir_fan_alias_to_protocol_vocabulary():
    """SmartIR files using min/mid/max map onto low/medium/high."""
    aliased = dict(CODESET, fanModes=["min", "mid", "max"])
    aliased["commands"] = {
        "off": B64_OFF,
        "cool": {
            level: {str(t): B64_COOL_22 for t in range(18, 25)}
            for level in ("min", "mid", "max")
        },
        "heat": {
            level: {str(t): B64_COOL_22 for t in range(18, 25)}
            for level in ("min", "mid", "max")
        },
    }
    with tempfile.TemporaryDirectory() as tmp:
        cls = make_codeset_protocol(_write_codeset(tmp, aliased))

    assert set(cls.fan_modes) == {"low", "medium", "high"}
    assert cls().encode(mode="cool", temp=22, fan="medium") == B64_COOL_22


def test_fan_only_mode_alias():
    """SmartIR 'fan' mode maps to Home Assistant's fan_only."""
    data = dict(CODESET, operationModes=["cool", "fan"])
    data["commands"] = {
        "off": B64_OFF,
        "cool": {"auto": {str(t): B64_COOL_22 for t in range(18, 25)}},
        "fan": {"auto": {str(t): B64_COOL_22 for t in range(18, 25)}},
    }
    with tempfile.TemporaryDirectory() as tmp:
        cls = make_codeset_protocol(_write_codeset(tmp, data))

    assert "fan_only" in cls.hvac_modes
    assert cls().encode(mode="fan_only", temp=22, fan="auto") == B64_COOL_22


if __name__ == "__main__":
    failures = 0
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            try:
                _fn()
                print(f"PASS {_name}")
            except Exception as _err:  # noqa: BLE001
                failures += 1
                print(f"FAIL {_name}: {_err}")
    print(f"\n{'FAILED' if failures else 'OK'} ({failures} failure(s))")
    sys.exit(1 if failures else 0)
