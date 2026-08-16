"""Abstract base class for IR climate protocols."""

from abc import ABC, abstractmethod


class BaseIRProtocol(ABC):
    """Base class for IR climate protocol encoders."""

    # Protocol metadata
    name: str = ""
    description: str = ""
    supported_models: list[str] = []

    # Temperature range
    min_temp: int = 16
    max_temp: int = 30

    # Default values
    default_temp: int = 22
    default_mode: str = "cool"
    default_fan: str = "auto"

    # HVAC modes supported by this protocol
    hvac_modes: list[str] = ["off", "cool", "heat", "dry", "fan_only", "auto"]

    # Fan modes supported by this protocol
    fan_modes: list[str] = ["auto", "low", "medium", "high"]

    # Swing support
    supports_swing: bool = False

    @abstractmethod
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

        Args:
            mode: HVAC mode (cool, heat, dry, fan_only, auto)
            temp: Target temperature in Celsius
            fan: Fan mode (auto, low, medium, high)
            power: Power state
            swing: Swing state
            command_format: Output format (raw, broadlink, pronto, etc.)

        Returns:
            IR command in the requested format
        """

    @abstractmethod
    def get_raw_timings(self, state: dict) -> list:
        """Get raw IR timings for a given state dict.

        Args:
            state: Dict with keys: mode, temp, fan, power, swing

        Returns:
            List of timings in microseconds (positive=mark, negative=space)
        """

    def encode_swing_toggle(self, command_format: str = "raw"):
        """Return a swing-toggle command, or None if the protocol has none.

        Protocols where swing is a stateless toggle (e.g. Transcold) override
        this. The climate entity sends it once when the swing mode changes
        instead of encoding swing into every state command.
        """
        return None

    def validate_state(self, mode: str, temp: int, fan: str) -> tuple[str, int, str]:
        """Validate and normalize climate state.

        Returns:
            Tuple of (mode, temp, fan)
        """
        if mode not in self.hvac_modes and mode != "off":
            mode = self.default_mode

        temp = min(max(temp, self.min_temp), self.max_temp)

        if fan not in self.fan_modes:
            fan = self.default_fan

        return mode, temp, fan
