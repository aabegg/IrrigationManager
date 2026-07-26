"""Serve and register the Irrigation Manager Lovelace cards."""

from asyncio import Lock
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from homeassistant.components.frontend import add_extra_js_url, remove_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace import LovelaceData
from homeassistant.components.lovelace.const import (
    CONF_RESOURCE_TYPE_WS,
    LOVELACE_DATA,
)
from homeassistant.components.lovelace.resources import ResourceStorageCollection
from homeassistant.const import CONF_ID, CONF_TYPE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from .const import DOMAIN

FRONTEND_DATA: Final = f"{DOMAIN}_frontend"
FRONTEND_URL_PATH: Final = f"/{DOMAIN}/frontend"
FRONTEND_FILE: Final = "dist/irrigation-manager.js"
FRONTEND_DIRECTORY: Final = Path(__file__).parent / "frontend"


@dataclass(slots=True)
class FrontendRegistration:
    """Track global static-path and per-entry module registration."""

    static_path_registered: bool = False
    entries: set[str] = field(default_factory=set)
    module_url: str | None = None
    extra_js_registered: bool = False
    lock: Lock = field(default_factory=Lock)


async def _async_register_module(hass: HomeAssistant, module_url: str) -> bool:
    """Persist the card as a Lovelace resource when storage mode is available."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if not isinstance(lovelace, LovelaceData) or not isinstance(
        lovelace.resources, ResourceStorageCollection
    ):
        return False

    resources = lovelace.resources
    await resources.async_get_info()
    module_path = module_url.partition("?")[0]
    existing = next(
        (
            item
            for item in resources.async_items()
            if str(item.get(CONF_URL, "")).partition("?")[0] == module_path
        ),
        None,
    )
    resource_data = {CONF_RESOURCE_TYPE_WS: "module", CONF_URL: module_url}
    if existing is None:
        await resources.async_create_item(resource_data)
    elif existing.get(CONF_URL) != module_url or existing.get(CONF_TYPE) != "module":
        await resources.async_update_item(existing[CONF_ID], resource_data)
    return True


async def async_register_frontend(hass: HomeAssistant, entry_id: str) -> None:
    """Register the card bundle once and track the config entry using it."""
    registration = hass.data.setdefault(FRONTEND_DATA, FrontendRegistration())
    if not isinstance(registration, FrontendRegistration):
        return

    async with registration.lock:
        if entry_id in registration.entries:
            return

        if not registration.static_path_registered:
            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(
                        FRONTEND_URL_PATH,
                        str(FRONTEND_DIRECTORY),
                        cache_headers=True,
                    )
                ]
            )
            registration.static_path_registered = True

        if not registration.entries:
            integration = await async_get_integration(hass, DOMAIN)
            version = str(integration.version or "0")
            registration.module_url = f"{FRONTEND_URL_PATH}/{FRONTEND_FILE}?v={version}"
            if not await _async_register_module(hass, registration.module_url):
                add_extra_js_url(hass, registration.module_url)
                registration.extra_js_registered = True

        registration.entries.add(entry_id)


async def async_unregister_frontend(hass: HomeAssistant, entry_id: str) -> None:
    """Remove the module URL when no loaded installation still needs it."""
    registration = hass.data.get(FRONTEND_DATA)
    if not isinstance(registration, FrontendRegistration):
        return

    async with registration.lock:
        registration.entries.discard(entry_id)
        if (
            not registration.entries
            and registration.module_url is not None
            and registration.extra_js_registered
        ):
            remove_extra_js_url(hass, registration.module_url)
            registration.extra_js_registered = False
        if not registration.entries:
            registration.module_url = None
