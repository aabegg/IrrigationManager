"""Initial-scope zone lifecycle, suspension, tariff, and maintenance tests."""

import asyncio
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_OFF, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.executor import ExecutionResult
from custom_components.irrigation_manager.models import ActiveExecutionState, MaintenanceTestState
from custom_components.irrigation_manager.storage import IrrigationStore


async def _setup(
    hass: HomeAssistant, *, measured: bool = False
) -> tuple[MockConfigEntry, ConfigSubentry]:
    """Set up one operationally complete but deterministic installation."""

    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], "on")

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        was_open = hass.states.get(entity_id).state == "on"
        hass.states.async_set(entity_id, STATE_OFF)
        if measured and was_open:
            hass.states.async_set(
                "sensor.water_meter",
                "2",
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
            )

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    data: dict[str, object] = {
        "name": "Garden",
        "operation_enabled": True,
        "automation_enabled": True,
        "water_tariff_per_m3": 2.5,
        "winter_reminder_date": "12-31",
        "maintenance_max_duration": 1,
        "maintenance_confirmation_interval": 1,
        "maintenance_tasks": [
            {
                "id": "filter",
                "name": "Clean filter",
                "first_due": "2026-01-01",
                "interval_days": 30,
            }
        ],
        "spring_checklist": [{"id": "valves", "name": "Inspect valves"}],
    }
    if measured:
        data["water_meter"] = "sensor.water_meter"
        hass.states.async_set(
            "sensor.water_meter",
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data=data,
        unique_id="installation-operational",
        version=2,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 1,
                "min_flow": 10,
                "max_flow": 10,
                "automation_enabled": True,
                "watering_mode": "demand",
                "area_m2": 10,
                "application_efficiency": 0.5,
                "maximum_deficit_mm": 50,
                "minimum_interval_days": 0,
                "maximum_interval_days": 1,
                "minimum_trigger_liters": 0.1,
                "minimum_effective_liters": 0.1,
                "maximum_target_liters": 100,
                "automatic_max_duration": 60,
                "watering_windows": ["00:00-23:59"],
            }
        ),
        subentry_id="subentry-lawn",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-lawn",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, zone


async def test_archive_restore_retains_identity_accounting_and_blocks_execution(
    hass: HomeAssistant,
) -> None:
    """Keep a zone's stable device/accounting state while excluding archived work."""
    entry, zone = await _setup(hass)
    manager = entry.runtime_data.manager
    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )
    total = manager._stored_state.zone_totals_liters["zone-lawn"]

    archived = await manager.async_set_zone_archived(
        zone_subentry_id=zone.subentry_id, archived=True
    )
    assert archived == {"zone_id": "zone-lawn", "archived": True}
    assert manager._stored_state.zone_totals_liters["zone-lawn"] == total
    with pytest.raises(HomeAssistantError, match="archived"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )
    assert (await manager.async_plan_automatic(dry_run=True))["would_create_request_ids"] == []

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    restarted = entry.runtime_data.manager
    assert "zone-lawn" in restarted._stored_state.archived_zones
    assert restarted._stored_state.zone_totals_liters["zone-lawn"] == total
    await restarted.async_set_zone_archived(zone_subentry_id=zone.subentry_id, archived=False)
    assert "zone-lawn" not in restarted._stored_state.archived_zones


async def test_timed_suspension_survives_restart_but_manual_irrigation_and_expiry_work(
    hass: HomeAssistant,
) -> None:
    """Suspend only automatic work and derive expiry from the durable timestamp."""
    entry, zone = await _setup(hass)
    manager = entry.runtime_data.manager
    manager._stored_state = manager._stored_state.__class__.from_dict(
        {
            **manager._stored_state.as_dict(),
            "zone_deficit_mm": {"zone-lawn": 10},
            "zone_last_effective_irrigation": {
                "zone-lawn": (datetime.now(UTC) - timedelta(days=2)).isoformat()
            },
        }
    )
    until = datetime.now(UTC) + timedelta(hours=1)
    await manager.async_suspend_automatic(until=until)
    assert (await manager.async_plan_automatic(dry_run=True))["would_create_request_ids"] == []
    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    restarted = entry.runtime_data.manager
    assert restarted._stored_state.automatic_suspended_until is not None
    await restarted.async_resume_automatic()
    assert restarted._stored_state.automatic_suspended_until is None


async def test_tariff_is_accounted_at_delivery_and_not_repriced(hass: HomeAssistant) -> None:
    """Book actual delivered cost once using the tariff active for that contribution."""
    entry, zone = await _setup(hass)
    manager = entry.runtime_data.manager
    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.06,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )
    delivered = manager._stored_state.zone_totals_liters["zone-lawn"]
    expected_cost = delivered * 2.5 / 1_000
    assert manager._stored_state.installation_cost == pytest.approx(expected_cost)
    assert manager._stored_state.zone_costs["zone-lawn"] == pytest.approx(expected_cost)
    assert manager._stored_state.water_consumption_history[-1].cost == pytest.approx(expected_cost)

    manager._installation_data["water_tariff_per_m3"] = 9
    manager._publish(status="idle", active_zone_id=None)
    assert manager._stored_state.installation_cost == pytest.approx(expected_cost)


async def test_recurring_maintenance_and_spring_state_are_durable(hass: HomeAssistant) -> None:
    """Retain due state, completion/snooze history, and checklist decisions."""
    entry, _ = await _setup(hass)
    manager = entry.runtime_data.manager
    listing = manager.list_maintenance(now=datetime(2026, 7, 22, tzinfo=UTC))
    assert listing["tasks"][0]["overdue"] is True

    completed = await manager.async_complete_maintenance_task(task_id="filter")
    completed_at = datetime.fromisoformat(
        str(manager._stored_state.maintenance_task_state["filter"]["last_completed_at"])
    )
    assert completed["next_due"] == (completed_at.date() + timedelta(days=30)).isoformat()
    await manager.async_snooze_maintenance_task(
        task_id="filter", until=date.today() + timedelta(days=40)
    )
    await manager.async_update_spring_checklist(item_id="valves", completed=True)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert [item["action"] for item in stored.maintenance_history] == [
        "completed",
        "snoozed",
    ]
    assert stored.spring_checklist_completed == ("valves",)

    await manager.async_set_winter_lock()
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.spring_checklist_completed == ()
    assert stored.spring_test_status == "not_started"


async def test_winter_activation_cannot_be_overwritten_by_finishing_spring_test(
    hass: HomeAssistant,
) -> None:
    """Finish cancellation before resetting spring state under the command lock."""
    entry, zone = await _setup(hass)
    manager = entry.runtime_data.manager
    started = asyncio.Event()
    cancelled = asyncio.Event()
    release = asyncio.Event()

    async def delayed_result(*_args, **_kwargs) -> ExecutionResult:
        started.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            cancelled.set()
            await release.wait()
        return ExecutionResult(
            zone_id="zone-lawn",
            delivered_liters=1,
            duration_seconds=1,
            target_reached=True,
            measurement_quality="estimated",
        )

    manager._executor.execute = AsyncMock(side_effect=delayed_result)
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=1,
        kind="spring_recommission",
    )
    await asyncio.wait_for(started.wait(), timeout=1)

    winter = asyncio.create_task(manager.async_set_winter_lock())
    await asyncio.wait_for(cancelled.wait(), timeout=1)
    release.set()
    await asyncio.wait_for(winter, timeout=1)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.winter_lock is True
    assert stored.maintenance_test is None
    assert stored.spring_checklist_completed == ()
    assert stored.spring_test_status == "not_started"


async def test_maintenance_test_can_attribute_measured_water_as_unassigned(
    hass: HomeAssistant,
) -> None:
    """Run a selected valve while intentionally leaving its measured water unassigned."""
    entry, zone = await _setup(hass, measured=True)
    manager = entry.runtime_data.manager
    manager._executor.execute = AsyncMock(
        return_value=ExecutionResult(
            zone_id="zone-lawn",
            delivered_liters=2,
            duration_seconds=10,
            target_reached=True,
            measurement_quality="measured",
        )
    )
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.01,
        water_attribution="unassigned",
    )
    task = manager._maintenance_task
    assert task is not None
    await task

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.unassigned_total_liters == pytest.approx(2)
    assert stored.zone_totals_liters.get("zone-lawn", 0) == 0
    assert stored.unassigned_cost == pytest.approx(0.005)
    assert stored.maintenance_test_history[-1]["water_attribution"] == "unassigned"


async def test_restart_preserves_unassigned_maintenance_attribution(
    hass: HomeAssistant,
) -> None:
    """Recover interrupted measured test water without changing its chosen attribution."""
    entry, zone = await _setup(hass, measured=True)
    assert await hass.config_entries.async_unload(entry.entry_id)
    now = datetime.now(UTC)
    state = await IrrigationStore(hass, entry.entry_id).async_load()
    test = MaintenanceTestState(
        test_id="restart-test",
        kind="maintenance",
        zone_id="zone-lawn",
        zone_subentry_id=zone.subentry_id,
        started_at=(now - timedelta(seconds=10)).isoformat(),
        expires_at=(now + timedelta(seconds=10)).isoformat(),
        confirmation_deadline=(now + timedelta(seconds=10)).isoformat(),
        water_attribution="unassigned",
    )
    state = state.__class__.from_dict(
        {
            **state.as_dict(),
            "maintenance_test": test.as_dict(),
            "active_execution": ActiveExecutionState(
                zone_id="zone-lawn",
                zone_valve="switch.lawn",
                main_valve=None,
                meter_raw_baseline_liters=0,
                prepared_at=(now - timedelta(seconds=10)).isoformat(),
                watering_started_at=(now - timedelta(seconds=5)).isoformat(),
                requested_duration_seconds=60,
                estimated_flow_l_min=10,
            ).as_dict(),
        }
    )
    await IrrigationStore(hass, entry.entry_id).async_save(state)
    hass.states.async_set(
        "sensor.water_meter",
        "2",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
    )
    hass.states.async_set("switch.lawn", "on")

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    recovered = await IrrigationStore(hass, entry.entry_id).async_load()
    assert recovered.unassigned_total_liters == pytest.approx(2)
    assert recovered.zone_totals_liters.get("zone-lawn", 0) == 0
    assert recovered.maintenance_test_history[-1]["result"] == "restart"
