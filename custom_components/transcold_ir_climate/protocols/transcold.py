"""Transcold IR protocol encoder."""

import base64
import struct

from .base import BaseIRProtocol


class TranscoldProtocol(BaseIRProtocol):
    """Transcold A/C IR protocol encoder.

    Ported from IRremoteESP8266.
    Supports: Transcold M1-F-NO-6 and compatible models.
    """

    name = "transcold"
    description = "Transcold A/C Protocol"
    supported_models = ["Transcold M1-F-NO-6"]

    min_temp = 18
    max_temp = 30
    default_temp = 22
    default_mode = "cool"
    default_fan = "auto"

    hvac_modes = ["off", "cool", "heat", "dry", "fan_only", "auto"]
    fan_modes = ["auto", "low", "medium", "high"]
    supports_swing = True

    # Protocol constants (from IRremoteESP8266)
    HDR_MARK = 5944
    HDR_SPACE = 7563
    BIT_MARK = 555
    ONE_SPACE = 3556
    ZERO_SPACE = 1526
    BITS = 24

    # Modes
    MODE_COOL = 0b0110
    MODE_DRY = 0b1100
    MODE_AUTO = 0b1110
    MODE_HEAT = 0b1010
    MODE_FAN = 0b0010

    # Fan speeds
    FAN_MIN = 0b1001
    FAN_MED = 0b1101
    FAN_MAX = 0b1011
    FAN_AUTO = 0b1111
    FAN_AUTO0 = 0b0110

    # Special states
    STATE_OFF = 0b111011110111100101010100  # 0xEF7D54
    STATE_SWING = 0b111001110110000101010100  # 0xE76554
    KNOWN_GOOD_STATE = 0xE96554

    # Temperature
    TEMP_MIN = 18
    TEMP_MAX = 30
    FAN_TEMP_CODE = 0b1111
    TEMP_SIZE = 4

    # Mapping
    HA_TO_TRANSCOLD_MODE = {
        "cool": MODE_COOL,
        "dry": MODE_DRY,
        "auto": MODE_AUTO,
        "heat": MODE_HEAT,
        "fan_only": MODE_FAN,
    }

    HA_TO_TRANSCOLD_FAN = {
        "low": FAN_MIN,
        "medium": FAN_MED,
        "high": FAN_MAX,
        "auto": FAN_AUTO,
    }

    @classmethod
    def _reverse_bits(cls, value: int, nbits: int) -> int:
        """Reverse bit order."""
        result = 0
        for i in range(nbits):
            result = (result << 1) | ((value >> i) & 1)
        return result

    @classmethod
    def _invert_bits(cls, value: int, nbits: int) -> int:
        """Invert bits."""
        return (~value) & ((1 << nbits) - 1)

    @classmethod
    def encode_temperature(cls, temp: int) -> int:
        """Encode temperature for Transcold protocol. Range: 18-30C."""
        temp = min(max(temp, cls.TEMP_MIN), cls.TEMP_MAX)
        temp_val = temp - cls.TEMP_MIN + 1
        return cls._reverse_bits(
            cls._invert_bits(temp_val, cls.TEMP_SIZE), cls.TEMP_SIZE
        )

    def build_state(
        self,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
    ) -> int:
        """Build a Transcold state from climate parameters. Returns 24-bit raw state."""
        if not power:
            return self.STATE_OFF

        if swing:
            return self.STATE_SWING

        transcold_mode = self.HA_TO_TRANSCOLD_MODE.get(mode, self.MODE_AUTO)
        transcold_fan = self.HA_TO_TRANSCOLD_FAN.get(fan, self.FAN_AUTO)

        # Adjust fan for mode constraints
        if mode in ("auto", "dry"):
            if transcold_fan == self.FAN_AUTO:
                transcold_fan = self.FAN_AUTO0
        else:
            if transcold_fan == self.FAN_AUTO0:
                transcold_fan = self.FAN_AUTO

        temp_bits = self.encode_temperature(temp)

        # Fan mode is a special case of Dry
        if mode == "fan_only":
            transcold_mode = self.MODE_DRY
            temp_bits = self.FAN_TEMP_CODE

        # Build 24-bit state: [Temp(4)][Mode(4)] [Fan(4)][0(4)] [0x54]
        byte0 = (temp_bits << 4) | transcold_mode
        byte1 = (transcold_fan << 4) | 0x0
        byte2 = 0x54

        return (byte0 << 16) | (byte1 << 8) | byte2

    def encode_to_raw_timings(self, state: int, nbits: int = BITS) -> list:
        """Encode Transcold state to raw IR timings (us). Positive=mark, negative=space."""
        timings = []

        # Header
        timings.append(self.HDR_MARK)
        timings.append(-self.HDR_SPACE)

        # Data: each byte sent as normal + inverted, LSB first
        for i in range(8, nbits + 1, 8):
            segment = (state >> (nbits - i)) & 0xFF
            both = (segment << 8) | ((~segment) & 0xFF)

            for b in range(16):
                bit = (both >> b) & 1
                timings.append(self.BIT_MARK)
                if bit:
                    timings.append(-self.ONE_SPACE)
                else:
                    timings.append(-self.ZERO_SPACE)

        # Footer
        timings.append(self.BIT_MARK)
        timings.append(-self.HDR_SPACE)
        timings.append(self.BIT_MARK)

        return timings

    def encode_to_broadlink(self, state: int, nbits: int = BITS) -> str:
        """Encode Transcold state to Broadlink Base64 format."""
        timings = self.encode_to_raw_timings(state, nbits)
        period = 32.84

        packet = bytearray()
        packet.append(0x26)  # IR
        packet.append(0x00)  # Repeat count

        bl_timings = bytearray()
        for t in timings:
            units = int(abs(t) / period)
            if units > 255:
                bl_timings.append(0x00)
                bl_timings.extend(struct.pack(">H", units))
            else:
                bl_timings.append(units)

        length = len(bl_timings)
        packet.extend(struct.pack("<H", length))
        packet.extend(bl_timings)
        packet.extend([0x0d, 0x05])

        return base64.b64encode(packet).decode("ascii")

    def encode(
        self,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
        command_format: str = "raw",
    ):
        """Encode climate state to IR command."""
        state = self.build_state(mode, temp, fan, power, swing)

        if command_format == "broadlink":
            return self.encode_to_broadlink(state)
        else:
            return self.encode_to_raw_timings(state)

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
