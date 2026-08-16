"""The Transcold IR Climate integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .api import async_register_views
from .const import DOMAIN, PLATFORMS
from .panel import async_register_panel, async_unregister_panel
from .protocols.import_helper import discover_custom_protocols


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Transcold IR Climate from a config entry."""
    store = hass.data.setdefault(DOMAIN, {})
    store[entry.entry_id] = entry.data

    # Discover custom protocols and SmartIR code sets at startup
    await hass.async_add_executor_job(discover_custom_protocols, hass)

    # Panel + HTTP API (both idempotent)
    async_register_views(hass)
    integration = await async_get_integration(hass, DOMAIN)
    await async_register_panel(hass, integration.version or "0")

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        remaining = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.entry_id != entry.entry_id
        ]
        if not remaining:
            async_unregister_panel(hass)
    return unload_ok
