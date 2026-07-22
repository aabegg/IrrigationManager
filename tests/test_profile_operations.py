"""Concurrency behavior for persisted profile operations."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import CONF_CUSTOM_PROFILES, DOMAIN
from custom_components.irrigation_manager.models import ManualIrrigationRequest


async def _setup_manager(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "unrelated_setting": "preserve-me"},
        unique_id="profile-races",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    manager = entry.runtime_data.manager
    for task in (manager._dispatcher_task, manager._automatic_planner_task):
        if task is not None:
            task.cancel()
    await asyncio.gather(
        *(task for task in (manager._dispatcher_task, manager._automatic_planner_task) if task),
        return_exceptions=True,
    )
    manager._dispatcher_task = None
    manager._automatic_planner_task = None
    return entry, manager


async def test_concurrent_profile_copies_preserve_both_and_unrelated_fresh_data(
    hass: HomeAssistant,
) -> None:
    """Serialize profile read-modify-write operations against fresh entry data."""
    entry, manager = await _setup_manager(hass)

    await asyncio.gather(
        manager.async_copy_profile(
            source_id="builtin:plant:generic-neutral:v1",
            new_id="plant:first",
            name="First",
        ),
        manager.async_copy_profile(
            source_id="builtin:plant:generic-neutral:v1",
            new_id="plant:second",
            name="Second",
        ),
    )

    assert set(entry.data[CONF_CUSTOM_PROFILES]) == {"plant:first", "plant:second"}
    assert entry.data["unrelated_setting"] == "preserve-me"


async def test_stale_profile_hash_rejects_copy_without_losing_concurrent_update(
    hass: HomeAssistant,
) -> None:
    """Make external profile edits visible instead of overwriting them."""
    entry, manager = await _setup_manager(hass)
    old_hash = manager.list_profiles()["config_hash"]
    concurrent_profiles = {
        "plant:external": {
            "kind": "plant",
            "name": "External",
            "values": {"seasonal_kc": [0.7] * 12},
        }
    }
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_CUSTOM_PROFILES: concurrent_profiles},
    )

    with pytest.raises(HomeAssistantError, match="changed"):
        await manager.async_copy_profile(
            source_id="builtin:plant:generic-neutral:v1",
            new_id="plant:stale-copy",
            name="Stale",
            expected_config_hash=str(old_hash),
        )

    assert entry.data[CONF_CUSTOM_PROFILES] == concurrent_profiles
    assert entry.data["unrelated_setting"] == "preserve-me"


async def test_profile_copy_during_open_operation_persists_but_runtime_stays_immutable(
    hass: HomeAssistant,
) -> None:
    """Defer applying a fresh profile config until the current snapshot is fully idle."""
    entry, manager = await _setup_manager(hass)
    now = datetime.now(UTC)
    pending = ManualIrrigationRequest(
        request_id="pending-operation",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="subentry-1",
        zone_name="Bed",
        zone_valve="switch.bed",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(pending,))
    manager._refresh_complete_idle_event()

    await manager.async_copy_profile(
        source_id="builtin:plant:generic-neutral:v1",
        new_id="plant:during-operation",
        name="During operation",
    )
    await asyncio.sleep(0)

    assert "plant:during-operation" in entry.data[CONF_CUSTOM_PROFILES]
    assert manager._installation_data[CONF_CUSTOM_PROFILES] == {}
    assert manager._pending_reload_task is not None
    assert not manager._pending_reload_task.done()
