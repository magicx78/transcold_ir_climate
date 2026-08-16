"""Transcold IR protocol encoder for Home Assistant.

Ported from IRremoteESP8266 (src/ir_Transcold.cpp / ir_Transcold.h)
https://github.com/crankyoldgit/IRremoteESP8266
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

        Returns the 24-bit raw state.
        """
        if not power:
            return TRANSCOLD_OFF

        if swing:
            return TRANSCOLD_SWING

        # Get mode
        transcold_mode = cls.MODE_MAP.get(mode, TRANSCOLD_MODE_AUTO)

        # Get fan speed
        transcold_fan = cls.FAN_MAP.get(fan, TRANSCOLD_FAN_AUTO)

        # Adjust fan for mode constraints
        if mode in ("auto", "dry"):
            if transcold_fan == TRANSCOLD_FAN_AUTO:
                transcold_fan = TRANSCOLD_FAN_AUTO0
        else:
            if transcold_fan == TRANSCOLD_FAN_AUTO0:
                transcold_fan = TRANSCOLD_FAN_AUTO

        # Encode temperature
        temp_bits = cls.encode_temperature(temp)

        # Fan mode is a special case of Dry
        if mode == "fan_only":
            transcold_mode = TRANSCOLD_MODE_DRY
            temp_bits = TRANSCOLD_FAN_TEMP_CODE

        # Build 24-bit state
        # Byte 0: [Temp(4)] [Mode(4)]
        # Byte 1: [Fan(4)]  [0(4)]
        # Byte 2: 0x54 (fixed)
        byte0 = (temp_bits << 4) | transcold_mode
        byte1 = (transcold_fan << 4) | 0x0
        byte2 = 0x54

        state = (byte0 << 16) | (byte1 << 8) | byte2
        return state

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

        # Data: each byte sent as normal + inverted, LSB first
        for i in range(8, nbits + 1, 8):
            segment = (state >> (nbits - i)) & 0xFF
            both = (segment << 8) | ((~segment) & 0xFF)

            # Send 16 bits, LSB first
            for b in range(16):
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

        return timings

    @classmethod
    def encode_to_broadlink(cls, state: int, nbits: int = TRANSCOLD_BITS) -> str:
        """Encode a Transcold state to Broadlink Base64 format.

        Broadlink protocol:
        - Header: 0x26 0x00 (repeat count)
        - Length: 2 bytes LE
        - Timings encoded as bytes (timing / 32.84us)
        - Footer: 0x0d 0x05
        """
        timings = cls.encode_to_raw_timings(state, nbits)

        # Broadlink uses a period of ~32.84us
        period = 32.84

        # Build packet
        packet = bytearray()
        packet.append(0x26)  # IR
        packet.append(0x00)  # Repeat count

        # Timing data
        bl_timings = bytearray()
        for t in timings:
            # Convert to Broadlink units
            units = int(abs(t) / period)
            if units > 255:
                # Use extended format for large timings
                bl_timings.append(0x00)
                bl_timings.extend(struct.pack(">H", units))
            else:
                bl_timings.append(units)

        # Length in bytes (little endian)
        length = len(bl_timings)
        packet.extend(struct.pack("<H", length))
        packet.extend(bl_timings)
        packet.extend([0x0d, 0x05])

        return base64.b64encode(packet).decode("ascii")

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
        state = cls.build_state(mode, temp, fan, power, swing)

        if command_format == "broadlink":
            return cls.encode_to_broadlink(state)
        else:
            return cls.encode_to_raw_timings(state)
