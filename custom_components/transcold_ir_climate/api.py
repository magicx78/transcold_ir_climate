"""HTTP API for the Transcold IR panel."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CODES_SUBDIR,
    CONF_ESPHOME_SERVICE,
    CONF_PROTOCOL,
    CONF_REMOTE_ENTITY,
    CUSTOM_PROTOCOLS_SUBDIR,
    DOMAIN,
)
from .protocols.import_helper import (
    discover_codesets,
    discover_custom_protocols,
    get_data_dir,
    get_protocol_info,
)
from .protocols.smartir_codeset import (
    SmartIRCodesetError,
    validate_smartir_climate,
)

_LOGGER = logging.getLogger(__name__)

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _check_admin(request: web.Request) -> web.Response | None:
    user = request.get("hass_user")
    if user is None or not user.is_admin:
        return web.json_response(
            {"error": "admin_required"}, status=web.HTTPUnauthorized.status_code
        )
    return None


def _safe_target(base: Path, filename: str, suffix: str) -> Path | None:
    """Resolve filename inside base, rejecting traversal and bad names."""
    name = Path(filename).name
    if not _SAFE_FILENAME.match(name) or not name.endswith(suffix):
        return None
    return base / name


class CodesetsView(HomeAssistantView):
    """List and import SmartIR code sets and custom protocol files."""

    url = f"/api/{DOMAIN}/codesets"
    name = f"api:{DOMAIN}:codesets"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        data_dir = await hass.async_add_executor_job(get_data_dir, hass)

        def _list() -> list[dict]:
            items = []
            for path in sorted((data_dir / CODES_SUBDIR).glob("*.json")):
                item = {"filename": path.name, "type": "smartir", "valid": True}
                try:
                    info = validate_smartir_climate(
                        json.loads(path.read_text(encoding="utf-8"))
                    )
                    item.update(info)
                    item["protocol"] = f"smartir_{path.stem}"
                except (SmartIRCodesetError, ValueError, OSError) as err:
                    item["valid"] = False
                    item["error"] = str(err)
                items.append(item)
            for path in sorted((data_dir / CUSTOM_PROTOCOLS_SUBDIR).glob("*.py")):
                items.append(
                    {"filename": path.name, "type": "python", "valid": True}
                )
            return items

        return self.json(
            {
                "items": await hass.async_add_executor_job(_list),
                "data_dir": str(data_dir),
            }
        )

    async def post(self, request: web.Request) -> web.Response:
        if (resp := _check_admin(request)) is not None:
            return resp
        hass: HomeAssistant = request.app["hass"]

        try:
            body = await request.json()
            filename = body["filename"]
            content = body["content"]
        except (ValueError, KeyError):
            return self.json({"error": "invalid_request"}, status_code=400)

        data_dir = await hass.async_add_executor_job(get_data_dir, hass)

        if filename.endswith(".json"):
            target = _safe_target(data_dir / CODES_SUBDIR, filename, ".json")
            if target is None:
                return self.json({"error": "invalid_filename"}, status_code=400)
            try:
                info = validate_smartir_climate(json.loads(content))
            except ValueError as err:
                return self.json(
                    {"error": "invalid_codeset", "detail": str(err)},
                    status_code=400,
                )
            await hass.async_add_executor_job(
                target.write_text, content, "utf-8"
            )
            await hass.async_add_executor_job(discover_codesets, hass)
            _LOGGER.info("Imported SmartIR code set %s", target.name)
            return self.json(
                {
                    "imported": target.name,
                    "protocol": f"smartir_{target.stem}",
                    **info,
                }
            )

        if filename.endswith(".py"):
            target = _safe_target(
                data_dir / CUSTOM_PROTOCOLS_SUBDIR, filename, ".py"
            )
            if target is None:
                return self.json({"error": "invalid_filename"}, status_code=400)
            await hass.async_add_executor_job(
                target.write_text, content, "utf-8"
            )
            await hass.async_add_executor_job(discover_custom_protocols, hass)
            _LOGGER.info("Imported custom protocol file %s", target.name)
            return self.json({"imported": target.name})

        return self.json({"error": "unsupported_file_type"}, status_code=400)


class CodesetDeleteView(HomeAssistantView):
    """Delete an imported file."""

    url = f"/api/{DOMAIN}/codesets/{{filename}}"
    name = f"api:{DOMAIN}:codesets:delete"
    requires_auth = True

    async def delete(self, request: web.Request, filename: str) -> web.Response:
        if (resp := _check_admin(request)) is not None:
            return resp
        hass: HomeAssistant = request.app["hass"]
        data_dir = await hass.async_add_executor_job(get_data_dir, hass)

        if filename.endswith(".json"):
            target = _safe_target(data_dir / CODES_SUBDIR, filename, ".json")
        elif filename.endswith(".py"):
            target = _safe_target(
                data_dir / CUSTOM_PROTOCOLS_SUBDIR, filename, ".py"
            )
        else:
            target = None
        if target is None:
            return self.json({"error": "invalid_filename"}, status_code=400)
        if not target.exists():
            return self.json({"error": "not_found"}, status_code=404)

        await hass.async_add_executor_job(target.unlink)
        await hass.async_add_executor_job(discover_codesets, hass)
        _LOGGER.info("Deleted imported file %s", filename)
        return self.json({"deleted": filename})


class ProtocolsView(HomeAssistantView):
    """List all registered protocols."""

    url = f"/api/{DOMAIN}/protocols"
    name = f"api:{DOMAIN}:protocols"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        # Refresh so newly copied files show up without a restart
        await hass.async_add_executor_job(discover_custom_protocols, hass)
        info = await hass.async_add_executor_job(get_protocol_info)
        return self.json({"protocols": info})


class DevicesView(HomeAssistantView):
    """List configured IR climate devices."""

    url = f"/api/{DOMAIN}/devices"
    name = f"api:{DOMAIN}:devices"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        hass: HomeAssistant = request.app["hass"]
        registry = er.async_get(hass)

        devices = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            entities = er.async_entries_for_config_entry(
                registry, entry.entry_id
            )
            entity_id = next(
                (e.entity_id for e in entities if e.domain == "climate"), None
            )
            state = hass.states.get(entity_id) if entity_id else None
            devices.append(
                {
                    "entry_id": entry.entry_id,
                    "title": entry.title,
                    "protocol": entry.data.get(CONF_PROTOCOL),
                    "remote_entity": entry.data.get(CONF_REMOTE_ENTITY),
                    "esphome_service": entry.data.get(CONF_ESPHOME_SERVICE),
                    "entity_id": entity_id,
                    "state": state.state if state else None,
                    "loaded": entry.state.value == "loaded",
                }
            )
        return self.json({"devices": devices})


def async_register_views(hass: HomeAssistant) -> None:
    """Register all HTTP views (idempotent via hass.data flag)."""
    store = hass.data.setdefault(DOMAIN, {})
    if store.get("views_registered"):
        return
    hass.http.register_view(CodesetsView())
    hass.http.register_view(CodesetDeleteView())
    hass.http.register_view(ProtocolsView())
    hass.http.register_view(DevicesView())
    store["views_registered"] = True
