"""Frontend bundle registration and serving tests."""

import asyncio

import pytest
from homeassistant.components.frontend import DATA_EXTRA_MODULE_URL
from homeassistant.components.lovelace import LovelaceData
from homeassistant.components.lovelace.const import CONF_RESOURCE_TYPE_WS, LOVELACE_DATA
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.frontend import (
    FRONTEND_DATA,
    FRONTEND_DIRECTORY,
    FRONTEND_FILE,
    FRONTEND_URL_PATH,
    FrontendRegistration,
    async_register_frontend,
    async_unregister_frontend,
)


async def test_frontend_bundle_is_served_registered_and_cleaned_up(
    hass: HomeAssistant, hass_client
) -> None:
    """Persist and update the versioned card module while installations are loaded."""
    assert await async_setup_component(hass, "lovelace", {})
    lovelace = hass.data[LOVELACE_DATA]
    assert isinstance(lovelace, LovelaceData)
    await lovelace.resources.async_create_item(
        {
            CONF_RESOURCE_TYPE_WS: "js",
            "url": f"{FRONTEND_URL_PATH}/{FRONTEND_FILE}?v=old",
        }
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registration = hass.data[FRONTEND_DATA]
    assert isinstance(registration, FrontendRegistration)
    assert registration.entries == {entry.entry_id}
    assert registration.module_url is not None
    integration = await async_get_integration(hass, DOMAIN)
    assert registration.module_url.endswith(f"irrigation-manager.js?v={integration.version}")
    await lovelace.resources.async_get_info()
    matching_resources = [
        resource
        for resource in lovelace.resources.async_items()
        if resource["url"].partition("?")[0] == f"{FRONTEND_URL_PATH}/{FRONTEND_FILE}"
    ]
    assert len(matching_resources) == 1
    assert any(
        resource["url"] == registration.module_url and resource["type"] == "module"
        for resource in matching_resources
    )
    assert registration.module_url not in hass.data[DATA_EXTRA_MODULE_URL].urls

    await async_register_frontend(hass, entry.entry_id)
    assert registration.entries == {entry.entry_id}

    client = await hass_client()
    response = await client.get(registration.module_url)
    assert response.status == 200
    bundle = await response.text()
    assert "irrigation-manager-overview-card" in bundle
    assert "irrigation-manager-zone-card" in bundle
    assert (FRONTEND_DIRECTORY / FRONTEND_FILE).is_file()

    module_url = registration.module_url
    await async_register_frontend(hass, "second-entry")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert any(resource["url"] == module_url for resource in lovelace.resources.async_items())

    await async_unregister_frontend(hass, "second-entry")
    assert any(resource["url"] == module_url for resource in lovelace.resources.async_items())


async def test_concurrent_entry_registration_registers_static_path_once(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Serialize the global static path while config entries set up concurrently."""
    assert await async_setup_component(hass, "frontend", {})
    assert hass.http is not None
    original_register = hass.http.async_register_static_paths
    first_register_started = asyncio.Event()
    allow_first_register = asyncio.Event()
    register_calls = 0

    async def controlled_register(configs) -> None:
        nonlocal register_calls
        register_calls += 1
        first_register_started.set()
        await allow_first_register.wait()
        await original_register(configs)

    monkeypatch.setattr(hass.http, "async_register_static_paths", controlled_register)

    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            title=f"Installation {index}",
            data={"name": f"Installation {index}"},
            unique_id=f"installation-{index}",
        )
        for index in (1, 2)
    ]
    for entry in entries:
        entry.add_to_hass(hass)

    first = asyncio.create_task(hass.config_entries.async_setup(entries[0].entry_id))
    await first_register_started.wait()
    # This is the exact registration call a second config-entry setup reaches.
    second_registration = asyncio.create_task(async_register_frontend(hass, entries[1].entry_id))
    await asyncio.sleep(0)
    assert register_calls == 1
    assert not second_registration.done()

    allow_first_register.set()
    first_result, _ = await asyncio.gather(first, second_registration)
    assert first_result is True

    registration = hass.data[FRONTEND_DATA]
    assert isinstance(registration, FrontendRegistration)
    assert registration.entries == {entry.entry_id for entry in entries}
    assert register_calls == 1
