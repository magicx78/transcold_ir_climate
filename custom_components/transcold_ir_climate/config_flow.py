"""Config flow for Transcold IR Climate integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import remote
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    DOMAIN,
    CONF_REMOTE_ENTITY,
    CONF_MIN_TEMP,
    CONF_MAX_TEMP,
    CONF_TARGET_TEMP,
    CONF_INITIAL_OPERATION_MODE,
    CONF_COMMAND_FORMAT,
    DEFAULT_NAME,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_INITIAL_OPERATION_MODE,
    DEFAULT_COMMAND_FORMAT,
    COMMAND_FORMAT_RAW,
    COMMAND_FORMAT_BROADLINK,
)


class TranscoldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transcold IR Climate."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(
                user_input[CONF_REMOTE_ENTITY]
            )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        # Get all remote entities
        remotes = [
            entity_id
            for entity_id in self.hass.states.async_entity_ids(remote.DOMAIN)
        ]

        if not remotes:
            return self.async_abort(
                reason="no_remotes",
                description_placeholders={},
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_REMOTE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="remote")
                ),
                vol.Optional(CONF_MIN_TEMP, default=DEFAULT_MIN_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(CONF_MAX_TEMP, default=DEFAULT_MAX_TEMP): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_TARGET_TEMP, default=DEFAULT_TARGET_TEMP
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_INITIAL_OPERATION_MODE,
                    default=DEFAULT_INITIAL_OPERATION_MODE,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=["off", "cool", "heat", "dry", "fan_only", "auto"],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_COMMAND_FORMAT, default=DEFAULT_COMMAND_FORMAT
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[COMMAND_FORMAT_RAW, COMMAND_FORMAT_BROADLINK],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return TranscoldOptionsFlow(config_entry)


class TranscoldOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Transcold IR Climate."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self.config_entry.data
        options = self.config_entry.options

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MIN_TEMP,
                    default=options.get(CONF_MIN_TEMP, data.get(CONF_MIN_TEMP, DEFAULT_MIN_TEMP)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_MAX_TEMP,
                    default=options.get(CONF_MAX_TEMP, data.get(CONF_MAX_TEMP, DEFAULT_MAX_TEMP)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_TARGET_TEMP,
                    default=options.get(CONF_TARGET_TEMP, data.get(CONF_TARGET_TEMP, DEFAULT_TARGET_TEMP)),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=16, max=30, step=1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional(
                    CONF_INITIAL_OPERATION_MODE,
                    default=options.get(
                        CONF_INITIAL_OPERATION_MODE,
                        data.get(CONF_INITIAL_OPERATION_MODE, DEFAULT_INITIAL_OPERATION_MODE),
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=["off", "cool", "heat", "dry", "fan_only", "auto"],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_COMMAND_FORMAT,
                    default=options.get(
                        CONF_COMMAND_FORMAT,
                        data.get(CONF_COMMAND_FORMAT, DEFAULT_COMMAND_FORMAT),
                    ),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=[COMMAND_FORMAT_RAW, COMMAND_FORMAT_BROADLINK],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)
