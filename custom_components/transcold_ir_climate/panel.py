"""Sidebar panel registration for Transcold IR Climate."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    FRONTEND_STATIC_URL,
    PANEL_COMPONENT_NAME,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)


def _get_lock(hass: HomeAssistant) -> asyncio.Lock:
    """Return the process-wide lock guarding panel (de)registration.

    Home Assistant sets up multiple config entries of the same domain
    concurrently, so the check-then-register sequence below needs a lock -
    without it, two entries starting at the same time both see
    "not registered yet" and both call panel_custom.async_register_panel(),
    which raises ValueError: Overwriting panel ... and fails that entry's
    setup entirely.
    """
    store = hass.data.setdefault(DOMAIN, {})
    return store.setdefault("panel_lock", asyncio.Lock())


async def async_register_panel(hass: HomeAssistant, version: str) -> None:
    """Serve the frontend assets and add the sidebar panel (idempotent)."""
    store = hass.data.setdefault(DOMAIN, {})
    async with _get_lock(hass):
        if store.get("panel_registered"):
            return

        frontend_path = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    FRONTEND_STATIC_URL, str(frontend_path), cache_headers=False
                )
            ]
        )

        await panel_custom.async_register_panel(
            hass,
            webcomponent_name=PANEL_COMPONENT_NAME,
            frontend_url_path=PANEL_URL_PATH,
            # Version in the URL busts the browser cache on updates
            module_url=f"{FRONTEND_STATIC_URL}/panel.js?v={version}",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=True,
            embed_iframe=False,
            config={},
        )
        store["panel_registered"] = True
        _LOGGER.debug("Registered sidebar panel /%s", PANEL_URL_PATH)


async def async_unregister_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel (when the last config entry unloads)."""
    store = hass.data.get(DOMAIN, {})
    async with _get_lock(hass):
        if store.get("panel_registered"):
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
            store["panel_registered"] = False
