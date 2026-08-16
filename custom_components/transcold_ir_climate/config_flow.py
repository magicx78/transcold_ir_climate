"""Config flow for Transcold IR Climate integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

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
    DEFAULT_NAME,
    DEFAULT_MIN_TEMP,
    DEFAULT_MAX_TEMP,
    DEFAULT_TARGET_TEMP,
    DEFAULT_INITIAL_OPERATION_MODE,
    DEFAULT_COMMAND_FORMAT,
    DEFAULT_PROTOCOL,
    COMMAND_FORMAT_RAW,
    COMMAND_FORMAT_BROADLINK,
)
from .protocols.import_helper import get_protocol_info


def _get_protocol_options(hass):
    """Get available protocols with descriptions."""
    from .protocols.import_helper import discover_custom_protocols
    discover_custom_protocols(hass)

    info = get_protocol_info()
    options = []
    for name in sorted(info.keys()):
        desc = info[name].get("description", name)
        models = info[name].get("supported_models", [])
        if models:
            label = f"{desc} ({', '.join(models)})"
        else:
            label = desc
        options.append({"value": name, "label": label})
    return options


class TranscoldConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Transcold IR Climate."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            target = user_input.get(CONF_REMOTE_ENTITY) or user_input.get(
                CONF_ESPHOME_SERVICE
            )
            if not target:
                errors["base"] = "need_target"
            else:
                await self.async_set_unique_id(
                    f"{target}_{user_input[CONF_PROTOCOL]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        # Discover protocols
        protocol_options = await self.hass.async_add_executor_job(
            _get_protocol_options, self.hass
        )

        if not protocol_options:
            return self.async_abort(reason="no_protocols")

        protocol_values = [p["value"] for p in protocol_options]

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): SelectSelector(
                    SelectSelectorConfig(
                        options=protocol_values,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="protocol",
                    )
                ),
                vol.Optional(CONF_REMOTE_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain="remote")
                ),
                vol.Optional(CONF_ESPHOME_SERVICE): TextSelector(),
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
        return TranscoldOptionsFlow()


class TranscoldOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Transcold IR Climate.

    Note: self.config_entry is provided by the OptionsFlow base class; it
    must NOT be assigned in __init__ (read-only property since HA 2024.12).
    """

    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
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
