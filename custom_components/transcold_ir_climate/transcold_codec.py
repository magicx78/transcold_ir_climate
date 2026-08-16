"""Transcold IR protocol encoder for Home Assistant.

Ported from IRremoteESP8266 (src/ir_Transcold.cpp / ir_Transcold.h)
https://github.com/crankyoldgit/IRremoteESP8266

NOTE: This module is the legacy standalone codec. The climate platform uses
protocols/transcold.py; both implement the identical (verified) wire format:

    24-bit state, MSB..LSB: [0xE (4)] [Fan (4)] [Mode (4)] [Temp (4)] [0x54 (8)]

Each byte is transmitted MSB-first followed by its bitwise inverse.
"""

import struct
import base64

from .const import (
    TRANSCOLD_HDR_MARK,
    TRANSCOLD_HDR_SPACE,
    TRANSCOLD_BIT_MARK,
    TRANSCOLD_ONE_SPACE,
    TRANSCOLD_ZERO_SPACE,
    TRANSCOLD_BITS,
    TRANSCOLD_MESSAGE_GAP,
    TRANSCOLD_MODE_COOL,
    TRANSCOLD_MODE_DRY,
    TRANSCOLD_MODE_AUTO,
    TRANSCOLD_MODE_HEAT,
    TRANSCOLD_MODE_FAN,
    TRANSCOLD_FAN_MIN,
    TRANSCOLD_FAN_MED,
    TRANSCOLD_FAN_MAX,
    TRANSCOLD_FAN_AUTO,
    TRANSCOLD_FAN_AUTO0,
    TRANSCOLD_STATE_PREFIX,
    TRANSCOLD_STATE_SUFFIX,
    TRANSCOLD_OFF,
    TRANSCOLD_SWING,
    TRANSCOLD_KNOWN_GOOD_STATE,
    TRANSCOLD_TEMP_MIN,
    TRANSCOLD_TEMP_MAX,
    TRANSCOLD_FAN_TEMP_CODE,
    TRANSCOLD_TEMP_SIZE,
)


class TranscoldCodec:
    """Encoder for Transcold A/C IR protocol."""

    # HA climate mode -> Transcold mode
    MODE_MAP = {
        "cool": TRANSCOLD_MODE_COOL,
        "dry": TRANSCOLD_MODE_DRY,
        "auto": TRANSCOLD_MODE_AUTO,
        "heat": TRANSCOLD_MODE_HEAT,
        "fan_only": TRANSCOLD_MODE_FAN,
    }

    # HA fan mode -> Transcold fan
    FAN_MAP = {
        "low": TRANSCOLD_FAN_MIN,
        "medium": TRANSCOLD_FAN_MED,
        "high": TRANSCOLD_FAN_MAX,
        "auto": TRANSCOLD_FAN_AUTO,
    }

    @staticmethod
    def _reverse_bits(value: int, nbits: int) -> int:
        """Reverse bit order."""
        result = 0
        for i in range(nbits):
            result = (result << 1) | ((value >> i) & 1)
        return result

    @staticmethod
    def _invert_bits(value: int, nbits: int) -> int:
        """Invert bits."""
        return (~value) & ((1 << nbits) - 1)

    @classmethod
    def encode_temperature(cls, temp: int) -> int:
        """Encode temperature for Transcold protocol.

        Range: 18-30°C
        """
        temp = min(max(temp, TRANSCOLD_TEMP_MIN), TRANSCOLD_TEMP_MAX)
        temp_val = temp - TRANSCOLD_TEMP_MIN + 1
        return cls._reverse_bits(
            cls._invert_bits(temp_val, TRANSCOLD_TEMP_SIZE), TRANSCOLD_TEMP_SIZE
        )

    @classmethod
    def build_state(
        cls,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
    ) -> int:
        """Build a Transcold state from climate parameters.

        Returns the 24-bit raw state. `swing` is ignored: Transcold swing is
        a stateless toggle command (TRANSCOLD_SWING), not part of the state.
        """
        if not power:
            return TRANSCOLD_OFF

        transcold_mode = cls.MODE_MAP.get(mode, TRANSCOLD_MODE_AUTO)
        transcold_fan = cls.FAN_MAP.get(fan, TRANSCOLD_FAN_AUTO)

        # Auto/Dry only allow FanAuto0; the other modes only FanAuto.
        if mode in ("auto", "dry"):
            if transcold_fan == TRANSCOLD_FAN_AUTO:
                transcold_fan = TRANSCOLD_FAN_AUTO0
        else:
            if transcold_fan == TRANSCOLD_FAN_AUTO0:
                transcold_fan = TRANSCOLD_FAN_AUTO

        temp_bits = cls.encode_temperature(temp)

        # Fan mode is a special case of Dry.
        if mode == "fan_only":
            transcold_mode = TRANSCOLD_MODE_DRY
            temp_bits = TRANSCOLD_FAN_TEMP_CODE

        # 24-bit state, MSB..LSB:
        # [prefix 0xE (4)] [Fan (4)] [Mode (4)] [Temp (4)] [0x54 (8)]
        return (
            (TRANSCOLD_STATE_PREFIX << 20)
            | (transcold_fan << 16)
            | (transcold_mode << 12)
            | (temp_bits << 8)
            | TRANSCOLD_STATE_SUFFIX
        )

    @classmethod
    def encode_to_raw_timings(cls, state: int, nbits: int = TRANSCOLD_BITS) -> list:
        """Encode a Transcold state to raw IR timings.

        Returns a list of timings in microseconds.
        Positive = mark, negative = space.
        """
        timings = []

        # Header
        timings.append(TRANSCOLD_HDR_MARK)
        timings.append(-TRANSCOLD_HDR_SPACE)

        # Data: bytes starting at the most significant byte; each byte is
        # followed by its inverse, all bits MSB-first (sendData MSBfirst=true).
        for i in range(8, nbits + 1, 8):
            segment = (state >> (nbits - i)) & 0xFF
            both = (segment << 8) | ((~segment) & 0xFF)

            for b in range(15, -1, -1):
                bit = (both >> b) & 1
                timings.append(TRANSCOLD_BIT_MARK)
                if bit:
                    timings.append(-TRANSCOLD_ONE_SPACE)
                else:
                    timings.append(-TRANSCOLD_ZERO_SPACE)

        # Footer
        timings.append(TRANSCOLD_BIT_MARK)
        timings.append(-TRANSCOLD_HDR_SPACE)
        timings.append(TRANSCOLD_BIT_MARK)
        timings.append(-TRANSCOLD_MESSAGE_GAP)

        return timings

    @classmethod
    def encode_to_broadlink(cls, state: int, nbits: int = TRANSCOLD_BITS) -> str:
        """Encode a Transcold state to Broadlink Base64 format.

        Broadlink packet:
        - 0x26 (IR), repeat count (0x00)
        - payload length, uint16 LE
        - pulses in 2^-15 s units (us * 269 / 8192); values > 255 as
          0x00 + uint16 BE
        The trailing MESSAGE_GAP space terminates the transmission.
        """
        timings = cls.encode_to_raw_timings(state, nbits)

        data = bytearray()
        for t in timings:
            units = max(1, round(abs(t) * 269 / 8192))
            if units > 255:
                data.append(0x00)
                data.extend(struct.pack(">H", units))
            else:
                data.append(units)

        packet = bytearray()
        packet.append(0x26)  # IR
        packet.append(0x00)  # Repeat count
        packet.extend(struct.pack("<H", len(data)))
        packet.extend(data)

        return base64.b64encode(bytes(packet)).decode("ascii")

    @classmethod
    def encode_swing_toggle(cls, command_format: str = "raw"):
        """Return the swing-toggle command (send once to flip swing)."""
        if command_format == "broadlink":
            return cls.encode_to_broadlink(TRANSCOLD_SWING)
        return cls.encode_to_raw_timings(TRANSCOLD_SWING)

    @classmethod
    def get_command(
        cls,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
        command_format: str = "raw",
    ):
        """Get IR command for given climate state.

        Returns raw timings list or broadlink base64 string.
        """
        state = cls.build_state(mode, temp, fan, power)

        if command_format == "broadlink":
            return cls.encode_to_broadlink(state)
        return cls.encode_to_raw_timings(state)
