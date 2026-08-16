"""Config flow for Transcold IR Climate integration."""

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
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


def _get_esphome_raw_targets(hass) -> list[dict]:
    """Find ESPHome actions matching this integration's raw-command contract.

    The integration calls the chosen esphome.* action with a single
    "command" variable (int[] raw timings, see README). There is no schema
    introspection available for that from the service registry, so we use
    a naming heuristic instead: any esphome action whose name contains
    "send_raw" was generated from a remote_transmitter.transmit_raw lambda
    with exactly that contract (this is how the built-in ir-proxy example
    in the README is set up). Actions like send_nec/send_samsung/... take
    protocol-specific variables (code, bits, ...) and are not compatible.
    """
    services = hass.services.async_services().get("esphome", {})
    return sorted(
        (
            {"value": f"esphome.{name}", "label": name.replace("_", " ").title()}
            for name in services
            if "send_raw" in name
        ),
        key=lambda option: option["label"],
    )


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

    def _remote_can_transmit_ir(self, remote_entity: str | None) -> bool:
        """Check that the chosen remote entity can actually emit IR.

        Only Broadlink remotes accept base64 IR payloads via
        remote.send_command. If no remote entity was chosen (ESPHome
        target instead), there is nothing to validate.
        """
        if not remote_entity:
            return True
        registry = er.async_get(self.hass)
        entry = registry.async_get(remote_entity)
        return entry is not None and entry.platform == "broadlink"

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            target = user_input.get(CONF_REMOTE_ENTITY) or user_input.get(
                CONF_ESPHOME_SERVICE
            )
            if not target:
                errors["base"] = "need_target"
            elif not self._remote_can_transmit_ir(
                user_input.get(CONF_REMOTE_ENTITY)
            ):
                # remote.send_command only reaches real IR blasters via the
                # Broadlink integration; TV/media remotes (Android TV, Apple
                # TV, ...) silently accept the call but cannot emit IR.
                errors[CONF_REMOTE_ENTITY] = "not_ir_remote"
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

        esphome_options = _get_esphome_raw_targets(self.hass)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PROTOCOL, default=DEFAULT_PROTOCOL): SelectSelector(
                    SelectSelectorConfig(
                        # {value, label} pairs so imported SmartIR code sets
                        # show manufacturer/model instead of the raw name
                        options=protocol_options,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(CONF_REMOTE_ENTITY): EntitySelector(
                    EntitySelectorConfig(
                        domain="remote", integration="broadlink"
                    )
                ),
                vol.Optional(CONF_ESPHOME_SERVICE): SelectSelector(
                    SelectSelectorConfig(
                        # Suggests discovered esphome.*send_raw* actions but
                        # still accepts free text for setups this heuristic
                        # cannot detect (e.g. a custom variable/service name).
                        options=esphome_options,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
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
