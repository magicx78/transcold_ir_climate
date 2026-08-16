"""Transcold IR protocol encoder.

Ported from IRremoteESP8266 (src/ir_Transcold.cpp / ir_Transcold.h)
https://github.com/crankyoldgit/IRremoteESP8266

Wire format (24 bits), verified against the C++ bitfield union and the raw
captures documented in ir_Transcold.h:

    MSB                                              LSB
    [0xE (4)] [Fan (4)] [Mode (4)] [Temp (4)] [0x54 (8)]

The C++ union is little endian, so the FIRST declared bitfield member holds
the LEAST significant bits:

    uint8_t      :8;   -> bits 0-7   = 0x54 (constant)
    uint8_t Temp :4;   -> bits 8-11
    uint8_t Mode :4;   -> bits 12-15
    uint8_t Fan  :4;   -> bits 16-19
    uint8_t      :4;   -> bits 20-23 = 0xE (constant)

Known good state 0xE96554 = Fan min (0b1001), Mode cool (0b0110), 22C.

On the wire each byte is sent MSB-first, immediately followed by its bitwise
inverse (sendData(..., both, 16, true) - the final `true` means MSB first!):
0xE9 -> 11101001 00010110.
"""

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
    MESSAGE_GAP = 100000  # kDefaultMessageGap: trailing space after the frame

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

    # Fixed nibbles present in every observed state
    STATE_PREFIX = 0xE  # bits 20-23
    STATE_SUFFIX = 0x54  # bits 0-7

    # Special full-state commands (sent verbatim, from ir_Transcold.h)
    STATE_OFF = 0b111011110111100101010100  # 0xEF7954
    STATE_SWING = 0b111001110110000101010100  # 0xE76154 (stateless toggle!)
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
        """Build a Transcold state from climate parameters. Returns 24-bit raw state.

        `swing` is ignored here: on Transcold, swing is a stateless toggle
        command (see encode_swing_toggle), not part of the regular state.
        """
        if not power:
            return self.STATE_OFF

        transcold_mode = self.HA_TO_TRANSCOLD_MODE.get(mode, self.MODE_AUTO)
        transcold_fan = self.HA_TO_TRANSCOLD_FAN.get(fan, self.FAN_AUTO)

        # Auto/Dry only allow FanAuto0; the other modes only FanAuto
        # (IRTranscoldAc::setFan modecheck).
        if mode in ("auto", "dry"):
            if transcold_fan == self.FAN_AUTO:
                transcold_fan = self.FAN_AUTO0
        else:
            if transcold_fan == self.FAN_AUTO0:
                transcold_fan = self.FAN_AUTO

        temp_bits = self.encode_temperature(temp)

        # Fan mode is a special case of Dry (IRTranscoldAc::setMode).
        if mode == "fan_only":
            transcold_mode = self.MODE_DRY
            temp_bits = self.FAN_TEMP_CODE

        return (
            (self.STATE_PREFIX << 20)
            | (transcold_fan << 16)
            | (transcold_mode << 12)
            | (temp_bits << 8)
            | self.STATE_SUFFIX
        )

    def encode_to_raw_timings(self, state: int, nbits: int = BITS) -> list:
        """Encode Transcold state to raw IR timings (us). Positive=mark, negative=space."""
        timings = []

        # Header
        timings.append(self.HDR_MARK)
        timings.append(-self.HDR_SPACE)

        # Data: bytes starting at the most significant byte; each byte is
        # followed by its inverse, all bits MSB-first (sendData MSBfirst=true).
        for i in range(8, nbits + 1, 8):
            segment = (state >> (nbits - i)) & 0xFF
            both = (segment << 8) | ((~segment) & 0xFF)

            for b in range(15, -1, -1):
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
        timings.append(-self.MESSAGE_GAP)

        return timings

    def encode_to_broadlink(self, state: int, nbits: int = BITS) -> str:
        """Encode Transcold state to Broadlink Base64 format.

        Broadlink pulse units are 2^-15 s (~30.46 us); the canonical
        conversion is units = us * 269 / 8192. Values > 255 are encoded as
        0x00 followed by a big-endian uint16. The trailing MESSAGE_GAP space
        terminates the transmission (encoded as an extended value).
        """
        timings = self.encode_to_raw_timings(state, nbits)

        data = bytearray()
        for t in timings:
            units = max(1, round(abs(t) * 269 / 8192))
            if units > 255:
                data.append(0x00)
                data.extend(struct.pack(">H", units))
            else:
                data.append(units)

        packet = bytearray()
        packet.append(0x26)  # 0x26 = IR
        packet.append(0x00)  # Repeat count
        packet.extend(struct.pack("<H", len(data)))  # Payload length (LE)
        packet.extend(data)

        return base64.b64encode(bytes(packet)).decode("ascii")

    def encode_swing_toggle(self, command_format: str = "raw"):
        """Return the swing-toggle command.

        Transcold swing is a stateless toggle: send it once to flip the
        current swing state. It must NOT be sent with every state change.
        """
        if command_format == "broadlink":
            return self.encode_to_broadlink(self.STATE_SWING)
        return self.encode_to_raw_timings(self.STATE_SWING)

    def encode(
        self,
        mode: str,
        temp: int,
        fan: str,
        power: bool = True,
        swing: bool = False,
        command_format: str = "raw",
    ):
        """Encode climate state to IR command.

        `swing` is accepted for API compatibility but ignored; use
        encode_swing_toggle() to flip the swing state.
        """
        state = self.build_state(mode, temp, fan, power)

        if command_format == "broadlink":
            return self.encode_to_broadlink(state)
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
