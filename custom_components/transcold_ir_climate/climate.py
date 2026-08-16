"""Climate platform for Transcold IR Climate integration."""

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    FAN_AUTO,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_HIGH,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_ESPHOME_SERVICE,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TARGET_TEMP,
    CONF_INITIAL_OPERATION_MODE,
    CONF_COMMAND_FORMAT,
    CONF_PROTOCOL,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_INITIAL_OPERATION_MODE,
    DEFAULT_COMMAND_FORMAT,
    DEFAULT_PROTOCOL,
    COMMAND_FORMAT_RAW,
    COMMAND_FORMAT_BROADLINK,
)
from .protocols import get_protocol
from .protocols.import_helper import discover_custom_protocols

_LOGGER = logging.getLogger(__name__)

HA_TO_PROTOCOL_MODE = {
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan_only",
    HVACMode.AUTO: "auto",
}

HA_TO_PROTOCOL_FAN = {
    FAN_AUTO: "auto",
    FAN_LOW: "low",
    FAN_MEDIUM: "medium",
    FAN_HIGH: "high",
}

PROTOCOL_TO_HA_FAN = {v: k for k, v in HA_TO_PROTOCOL_FAN.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transcold climate platform."""
    # Discover custom protocols first
    await hass.async_add_executor_job(discover_custom_protocols, hass)

    data = config_entry.data
    options = config_entry.options

    name = data.get(CONF_NAME, "IR Klima")
    remote_entity = data.get(CONF_REMOTE_ENTITY)
    esphome_service = data.get(CONF_ESPHOME_SERVICE)
    protocol_name = data.get(CONF_PROTOCOL, DEFAULT_PROTOCOL)
    min_temp = options.get(CONF_MIN_TEMP, data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP))
    max_temp = options.get(CONF_MAX_TEMP, data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP))
    target_temp = options.get(
        CONF_TARGET_TEMP, data.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)
    )
    initial_mode = options.get(
        CONF_INITIAL_OPERATION_MODE,
        data.get(CONF_INITIAL_OPERATION_MODE, DEFAULT_INITIAL_OPERATION_MODE),
    )
    command_format = options.get(
        CONF_COMMAND_FORMAT,
        data.get(CONF_COMMAND_FORMAT, DEFAULT_COMMAND_FORMAT),
    )

    if not remote_entity and not esphome_service:
        _LOGGER.error(
            "No IR target configured: set either a remote entity or an "
            "ESPHome service"
        )
        return

    # Get protocol instance
    try:
        protocol = await hass.async_add_executor_job(get_protocol, protocol_name)
    except ValueError as err:
        _LOGGER.error("Failed to load protocol %s: %s", protocol_name, err)
        return

    entity = IRClimateEntity(
        hass,
        config_entry.entry_id,
        name,
        remote_entity,
        esphome_service,
        protocol,
        min_temp,
        max_temp,
        target_temp,
        initial_mode,
        command_format,
    )

    async_add_entities([entity])


class IRClimateEntity(ClimateEntity):
    """Representation of an IR Climate device."""

    _attr_has_entity_name = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    # IR is one-way: HA can never verify the real device state.
    _attr_assumed_state = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        remote_entity: str | None,
        esphome_service: str | None,
        protocol,
        min_temp: int,
        max_temp: int,
        target_temp: int,
        initial_mode: str,
        command_format: str,
    ) -> None:
        """Initialize the climate device."""
        self.hass = hass
        self._entry_id = entry_id
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}_climate"
        self._remote_entity = remote_entity
        self._esphome_service = esphome_service
        self._remote_platform: str | None = None
        self._protocol = protocol
        self._command_format = command_format

        # Set temperature range from protocol or config
        self._min_temp = max(min_temp, protocol.min_temp)
        self._max_temp = min(max_temp, protocol.max_temp)

        # Build HVAC modes
        self._attr_hvac_modes = [HVACMode.OFF]
        mode_map = {
            "cool": HVACMode.COOL,
            "heat": HVACMode.HEAT,
            "dry": HVACMode.DRY,
            "fan_only": HVACMode.FAN_ONLY,
            "auto": HVACMode.AUTO,
        }
        for mode in protocol.hvac_modes:
            if mode != "off" and mode in mode_map:
                self._attr_hvac_modes.append(mode_map[mode])

        # Build fan modes
        self._attr_fan_modes = []
        for fan in protocol.fan_modes:
            if fan in PROTOCOL_TO_HA_FAN:
                self._attr_fan_modes.append(PROTOCOL_TO_HA_FAN[fan])

        # Swing modes
        if protocol.supports_swing:
            self._attr_swing_modes = ["off", "on"]
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.FAN_MODE
                | ClimateEntityFeature.SWING_MODE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )
        else:
            self._attr_swing_modes = []
            self._attr_supported_features = (
                ClimateEntityFeature.TARGET_TEMPERATURE
                | ClimateEntityFeature.FAN_MODE
                | ClimateEntityFeature.TURN_ON
                | ClimateEntityFeature.TURN_OFF
            )

        # Internal state
        self._hvac_mode = HVACMode.OFF
        self._target_temperature = min(max(target_temp, self._min_temp), self._max_temp)
        self._fan_mode = PROTOCOL_TO_HA_FAN.get(protocol.default_fan, FAN_AUTO)
        self._swing_mode = "off"
        self._power = False

        # Apply initial mode
        if initial_mode != "off":
            ha_mode = mode_map.get(initial_mode, HVACMode.COOL)
            if ha_mode in self._attr_hvac_modes:
                self._hvac_mode = ha_mode
                self._power = True

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._min_temp

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._max_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return hvac operation mode."""
        return self._hvac_mode

    @property
    def fan_mode(self) -> str | None:
        """Return the fan setting."""
        return self._fan_mode

    @property
    def swing_mode(self) -> str | None:
        """Return the swing setting."""
        return self._swing_mode

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVACMode.OFF:
            self._power = False
            self._hvac_mode = HVACMode.OFF
        else:
            self._power = True
            self._hvac_mode = hvac_mode

        await self._send_command()
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._target_temperature = int(temp)
            if self._power:
                await self._send_command()
            self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        self._fan_mode = fan_mode
        if self._power:
            await self._send_command()
        self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing mode.

        Transcold swing is a stateless toggle command: it is sent exactly
        once when the swing mode changes. Sending the full state afterwards
        is not needed (and would not encode swing anyway).
        """
        changed = swing_mode != self._swing_mode
        self._swing_mode = swing_mode

        if changed and self._power:
            fmt = self._effective_command_format()
            toggle = self._protocol.encode_swing_toggle(command_format=fmt)
            if toggle is not None:
                await self._async_transmit(toggle)
            else:
                # Protocol encodes swing in the regular state instead.
                await self._send_command()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        self._power = True
        if self._hvac_mode == HVACMode.OFF:
            # Find first non-off mode
            for mode in self._attr_hvac_modes:
                if mode != HVACMode.OFF:
                    self._hvac_mode = mode
                    break
        await self._send_command()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        self._power = False
        self._hvac_mode = HVACMode.OFF
        await self._send_command()
        self.async_write_ha_state()

    def _resolve_remote_platform(self) -> str | None:
        """Look up which integration provides the target remote entity."""
        if not self._remote_entity:
            return None
        if self._remote_platform is None:
            registry = er.async_get(self.hass)
            entry = registry.async_get(self._remote_entity)
            self._remote_platform = entry.platform if entry else "unknown"
            _LOGGER.debug(
                "Remote %s is provided by platform %s",
                self._remote_entity,
                self._remote_platform,
            )
        return self._remote_platform

    def _effective_command_format(self) -> str:
        """Determine the wire format for the configured IR target.

        Broadlink remotes only accept learned command names or base64
        ("b64:...") via remote.send_command - raw timing lists never work
        there, so we auto-upgrade "raw" to "broadlink" for them.
        """
        if self._esphome_service:
            return COMMAND_FORMAT_RAW
        if self._command_format == COMMAND_FORMAT_BROADLINK:
            return COMMAND_FORMAT_BROADLINK
        if self._resolve_remote_platform() == "broadlink":
            return COMMAND_FORMAT_BROADLINK
        return self._command_format

    async def _async_transmit(self, command) -> None:
        """Send an encoded IR command to the configured target."""
        if self._esphome_service:
            # ESPHome user-defined action, e.g. esphome.ir_proxy_send_raw_command
            # with a variable named "command" of type int[].
            domain, _, service = self._esphome_service.partition(".")
            if not service:
                domain, service = "esphome", self._esphome_service
            await self.hass.services.async_call(
                domain, service, {"command": command}, blocking=True
            )
            return

        if isinstance(command, str):
            # Broadlink base64 payloads need the "b64:" prefix, otherwise the
            # integration treats them as learned command names.
            if not command.startswith("b64:"):
                command = f"b64:{command}"
        else:
            _LOGGER.error(
                "remote.send_command cannot transmit raw timing lists to %s "
                "(platform %s). Use a Broadlink remote (base64) or configure "
                "an ESPHome service instead",
                self._remote_entity,
                self._resolve_remote_platform(),
            )
            return

        await self.hass.services.async_call(
            "remote",
            "send_command",
            {"entity_id": self._remote_entity, "command": command},
            blocking=True,
        )

    async def _send_command(self) -> None:
        """Encode the current state and transmit it."""
        protocol_mode = HA_TO_PROTOCOL_MODE.get(self._hvac_mode, "cool")
        protocol_fan = HA_TO_PROTOCOL_FAN.get(self._fan_mode, "auto")
        fmt = self._effective_command_format()

        try:
            command = self._protocol.encode(
                mode=protocol_mode,
                temp=int(self._target_temperature),
                fan=protocol_fan,
                power=self._power,
                command_format=fmt,
            )
        except Exception as err:
            _LOGGER.error("Error encoding IR command: %s", err)
            return

        try:
            await self._async_transmit(command)
            _LOGGER.debug(
                "Sent IR command (%s/%s): mode=%s, temp=%s, fan=%s, power=%s",
                self._protocol.name,
                fmt,
                protocol_mode,
                self._target_temperature,
                protocol_fan,
                self._power,
            )
        except Exception as err:
            _LOGGER.error("Error sending IR command: %s", err)
