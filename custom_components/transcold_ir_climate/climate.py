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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TARGET_TEMP,
    CONF_INITIAL_OPERATION_MODE,
    CONF_COMMAND_FORMAT,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_INITIAL_OPERATION_MODE,
    DEFAULT_COMMAND_FORMAT,
    COMMAND_FORMAT_RAW,
)
from .transcold_codec import TranscoldCodec

_LOGGER = logging.getLogger(__name__)

HA_TO_TRANSCOLD_MODE = {
    HVACMode.COOL: "cool",
    HVACMode.HEAT: "heat",
    HVACMode.DRY: "dry",
    HVACMode.FAN_ONLY: "fan_only",
    HVACMode.AUTO: "auto",
}

TRANSCOLD_TO_HA_MODE = {v: k for k, v in HA_TO_TRANSCOLD_MODE.items()}

HA_TO_TRANSCOLD_FAN = {
    FAN_AUTO: "auto",
    FAN_LOW: "low",
    FAN_MEDIUM: "medium",
    FAN_HIGH: "high",
}

TRANSCOLD_TO_HA_FAN = {v: k for k, v in HA_TO_TRANSCOLD_FAN.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Transcold climate platform."""
    data = config_entry.data
    options = config_entry.options

    name = data.get(CONF_NAME, "Transcold Klima")
    remote_entity = data[CONF_REMOTE_ENTITY]
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

    entity = TranscoldClimate(
        hass,
        config_entry.entry_id,
        name,
        remote_entity,
        min_temp,
        max_temp,
        target_temp,
        initial_mode,
        command_format,
    )

    async_add_entities([entity], update_before_add=True)


class TranscoldClimate(ClimateEntity):
    """Representation of a Transcold IR Climate device."""

    _attr_has_entity_name = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        name: str,
        remote_entity: str,
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
        self._min_temp = min_temp
        self._max_temp = max_temp
        self._command_format = command_format

        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.COOL,
            HVACMode.HEAT,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.AUTO,
        ]
        self._attr_fan_modes = [FAN_AUTO, FAN_LOW, FAN_MEDIUM, FAN_HIGH]
        self._attr_swing_modes = ["off", "on"]

        # Internal state
        self._hvac_mode = HVACMode.OFF
        self._target_temperature = target_temp
        self._fan_mode = FAN_AUTO
        self._swing_mode = "off"
        self._power = False

        # Apply initial mode
        if initial_mode != "off":
            self._hvac_mode = TRANSCOLD_TO_HA_MODE.get(initial_mode, HVACMode.COOL)
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
        """Set new target swing mode."""
        self._swing_mode = swing_mode
        if self._power:
            await self._send_command()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        self._power = True
        if self._hvac_mode == HVACMode.OFF:
            self._hvac_mode = HVACMode.COOL
        await self._send_command()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        self._power = False
        self._hvac_mode = HVACMode.OFF
        await self._send_command()
        self.async_write_ha_state()

    async def _send_command(self) -> None:
        """Send IR command via remote.send_command service."""
        transcold_mode = HA_TO_TRANSCOLD_MODE.get(self._hvac_mode, "cool")
        transcold_fan = HA_TO_TRANSCOLD_FAN.get(self._fan_mode, "auto")
        swing = self._swing_mode == "on"

        try:
            command = TranscoldCodec.get_command(
                mode=transcold_mode,
                temp=int(self._target_temperature),
                fan=transcold_fan,
                power=self._power,
                swing=swing,
                command_format=self._command_format,
            )
        except Exception as err:
            _LOGGER.error("Error encoding Transcold command: %s", err)
            return

        service_data = {
            "entity_id": self._remote_entity,
        }

        if self._command_format == COMMAND_FORMAT_RAW:
            service_data["command"] = command
        else:
            service_data["command"] = command

        try:
            await self.hass.services.async_call(
                "remote", "send_command", service_data, blocking=False
            )
            _LOGGER.debug(
                "Sent Transcold command: mode=%s, temp=%s, fan=%s, power=%s, swing=%s",
                transcold_mode,
                self._target_temperature,
                transcold_fan,
                self._power,
                swing,
            )
        except Exception as err:
            _LOGGER.error("Error sending IR command: %s", err)
