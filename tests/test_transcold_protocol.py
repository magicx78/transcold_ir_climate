"""Tests for the Transcold IR protocol encoder.

Runs standalone (no Home Assistant required):

    python tests/test_transcold_protocol.py

or via pytest. The reference implementation below is a literal transcription
of IRsend::sendTranscold + IRsend::sendData from IRremoteESP8266
(src/ir_Transcold.cpp, src/IRsend.cpp) and is kept intentionally independent
of the integration code so both can be compared against each other.
"""

import base64
import importlib.util
import struct
import sys
import types
from pathlib import Path

COMPONENT_DIR = Path(__file__).resolve().parent.parent / (
    "custom_components/transcold_ir_climate"
)

# Import protocols package directly (its modules have no HA dependencies),
# bypassing custom_components/transcold_ir_climate/__init__.py which imports
# homeassistant.
sys.path.insert(0, str(COMPONENT_DIR))
from protocols.transcold import TranscoldProtocol  # noqa: E402

# Load const.py + transcold_codec.py as a synthetic package so the codec's
# relative import works without pulling in homeassistant.
_pkg = types.ModuleType("tic")
_pkg.__path__ = [str(COMPONENT_DIR)]
sys.modules["tic"] = _pkg
for _mod in ("const", "transcold_codec"):
    _spec = importlib.util.spec_from_file_location(
        f"tic.{_mod}", COMPONENT_DIR / f"{_mod}.py"
    )
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[f"tic.{_mod}"] = _module
    _spec.loader.exec_module(_module)
TranscoldCodec = sys.modules["tic.transcold_codec"].TranscoldCodec


# --- Reference: literal transcription of the C++ code ----------------------

HDR_MARK = 5944
HDR_SPACE = 7563
BIT_MARK = 555
ONE_SPACE = 3556
ZERO_SPACE = 1526
MESSAGE_GAP = 100000  # kDefaultMessageGap


def cpp_send_data(timings, onemark, onespace, zeromark, zerospace, data, nbits,
                  msb_first):
    """IRsend::sendData transcribed from IRsend.cpp."""
    if nbits == 0:
        return
    if msb_first:
        mask = 1 << (nbits - 1)
        while mask:
            if data & mask:
                timings.append(onemark)
                timings.append(-onespace)
            else:
                timings.append(zeromark)
                timings.append(-zerospace)
            mask >>= 1
    else:
        for _ in range(nbits):
            if data & 1:
                timings.append(onemark)
                timings.append(-onespace)
            else:
                timings.append(zeromark)
                timings.append(-zerospace)
            data >>= 1


def cpp_send_transcold(data, nbits=24):
    """IRsend::sendTranscold transcribed from ir_Transcold.cpp."""
    assert nbits % 8 == 0
    timings = []
    # Header
    timings.append(HDR_MARK)
    timings.append(-HDR_SPACE)
    # Data: MSB byte first; each byte normal then inverted; the combined
    # 16 bits are sent via sendData(..., true) => MSB first.
    for i in range(8, nbits + 1, 8):
        segment = (data >> (nbits - i)) & 0xFF
        both = (segment << 8) | (~segment & 0xFF)
        cpp_send_data(timings, BIT_MARK, ONE_SPACE, BIT_MARK, ZERO_SPACE,
                      both, 16, True)
    # Footer
    timings.append(BIT_MARK)
    timings.append(-HDR_SPACE)
    timings.append(BIT_MARK)
    timings.append(-MESSAGE_GAP)
    return timings


# --- Tests ------------------------------------------------------------------

PROTO = TranscoldProtocol()


def test_known_good_state():
    # kTranscoldKnownGoodState = 0xE96554 = cool / 22C / fan min.
    assert PROTO.build_state("cool", 22, "low") == 0xE96554


def test_states_from_ir_transcold_h_captures():
    # Raw captures documented in ir_Transcold.h:
    #   "Cool Mode 24, low":  11101001 00010110 01100001 ... -> E9 61 54
    #   "Auto Mode,   low":   11101001 00010110 11100001 ... -> E9 E1 54
    assert PROTO.build_state("cool", 24, "low") == 0xE96154
    assert PROTO.build_state("auto", 24, "low") == 0xE9E154


def test_special_states():
    # Binary literals from ir_Transcold.h.
    assert PROTO.STATE_OFF == 0xEF7954
    assert PROTO.STATE_SWING == 0xE76154
    assert PROTO.build_state("cool", 22, "low", power=False) == 0xEF7954


def test_fan_constraints():
    # Auto/Dry use FanAuto0 when fan=auto; other modes use FanAuto.
    auto_state = PROTO.build_state("auto", 22, "auto")
    assert (auto_state >> 16) & 0xF == PROTO.FAN_AUTO0
    cool_state = PROTO.build_state("cool", 22, "auto")
    assert (cool_state >> 16) & 0xF == PROTO.FAN_AUTO


def test_fan_only_is_dry_with_temp_code():
    state = PROTO.build_state("fan_only", 22, "auto")
    assert (state >> 12) & 0xF == PROTO.MODE_DRY
    assert (state >> 8) & 0xF == PROTO.FAN_TEMP_CODE


def test_temperature_encoding():
    # 22C -> value 5 -> invert 1010 -> reverse 0101 = 5.
    assert PROTO.encode_temperature(22) == 0b0101
    # 24C -> value 7 -> invert 1000 -> reverse 0001 = 1 (matches captures).
    assert PROTO.encode_temperature(24) == 0b0001
    # Clamping.
    assert PROTO.encode_temperature(10) == PROTO.encode_temperature(18)
    assert PROTO.encode_temperature(99) == PROTO.encode_temperature(30)


def test_raw_timings_match_cpp_reference():
    cases = [
        PROTO.build_state("cool", 22, "low"),
        PROTO.build_state("cool", 24, "auto"),
        PROTO.build_state("heat", 30, "high"),
        PROTO.build_state("dry", 18, "auto"),
        PROTO.build_state("auto", 25, "medium"),
        PROTO.build_state("fan_only", 22, "auto"),
        PROTO.STATE_OFF,
        PROTO.STATE_SWING,
        0xE96554,
    ]
    for state in cases:
        expected = cpp_send_transcold(state)
        actual = PROTO.encode_to_raw_timings(state)
        assert actual == expected, f"raw timings mismatch for 0x{state:06X}"
        # Codec module must produce the identical stream.
        assert TranscoldCodec.encode_to_raw_timings(state) == expected


def test_first_data_bit_is_msb():
    # 0xE9... -> first data bit is 1 -> ONE_SPACE right after the header.
    timings = PROTO.encode_to_raw_timings(0xE96554)
    assert timings[0] == HDR_MARK
    assert timings[1] == -HDR_SPACE
    assert timings[2] == BIT_MARK
    assert timings[3] == -ONE_SPACE  # MSB of 0xE9 is 1


def test_raw_timing_structure():
    timings = PROTO.encode_to_raw_timings(0xE96554)
    # header(2) + 24 bits * 2 (normal+inverted) * 2 values + footer(4)
    assert len(timings) == 2 + 48 * 2 + 4
    assert timings[-1] == -MESSAGE_GAP


def test_broadlink_packet():
    b64 = PROTO.encode_to_broadlink(0xE96554)
    packet = base64.b64decode(b64)

    assert packet[0] == 0x26  # IR marker
    assert packet[1] == 0x00  # no repeats
    length = struct.unpack("<H", packet[2:4])[0]
    payload = packet[4:]
    assert length == len(payload), "length field must cover the whole payload"

    # Decode pulses back to microseconds and compare with the raw timings.
    timings = PROTO.encode_to_raw_timings(0xE96554)
    decoded = []
    i = 0
    while i < len(payload):
        if payload[i] == 0x00:
            units = struct.unpack(">H", payload[i + 1:i + 3])[0]
            i += 3
        else:
            units = payload[i]
            i += 1
        decoded.append(units * 8192 / 269)
    assert len(decoded) == len(timings)
    for us, orig in zip(decoded, timings):
        # Round trip must stay within one Broadlink tick (~30.5 us).
        assert abs(us - abs(orig)) <= 8192 / 269, (us, orig)

    # Broadlink tick sanity: header mark 5944 us -> ~195 units (one byte);
    # with the old wrong 32.84 divisor it would have been 181.
    assert payload[0] == round(5944 * 269 / 8192) == 195


def test_broadlink_codec_matches_protocol():
    for state in (0xE96554, PROTO.STATE_OFF, PROTO.STATE_SWING):
        assert TranscoldCodec.encode_to_broadlink(state) == (
            PROTO.encode_to_broadlink(state)
        )


def test_swing_toggle():
    toggle = PROTO.encode_swing_toggle()
    assert toggle == cpp_send_transcold(PROTO.STATE_SWING)
    # encode() must NOT emit the swing state for regular commands.
    normal = PROTO.encode("cool", 22, "low", swing=True)
    assert normal == cpp_send_transcold(0xE96554)


def _main():
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as err:
                failed += 1
                print(f"FAIL  {name}: {err}")
    if failed:
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    _main()
