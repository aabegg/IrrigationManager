"""Winter, supervised maintenance, and calibration safety tests."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN, EVENT_IRRIGATION_MANAGER
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    MaintenanceTestState,
    StoredInstallationState,
)
from custom_components.irrigation_manager.storage import IrrigationStore


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(2):
        while not predicate():  # noqa: ASYNC110 - state changes have no dedicated test seam
            await asyncio.sleep(0.001)


async def _setup(
    hass: HomeAssistant,
    *,
    confirmation_interval: float = 0.03,
    max_duration: float = 1,
    measured: bool = False,
    with_flow: bool = True,
    measured_liters: float = 0.003,
) -> tuple[MockConfigEntry, ConfigSubentry, list[tuple[str, str]]]:
    operations: list[tuple[str, str]] = []

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("on", entity_id))
        hass.states.async_set(entity_id, STATE_ON)

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("off", entity_id))
        was_on = hass.states.get(entity_id).state == STATE_ON
        hass.states.async_set(entity_id, STATE_OFF)
        if measured and entity_id == "switch.lawn" and was_on:
            hass.states.async_set(
                "sensor.water_meter",
                str(measured_liters),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
            )

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    data: dict[str, object] = {
        "name": "Garden",
        "operation_enabled": True,
        "automation_enabled": True,
        "meter_type": "none",
        "leak_flow_threshold": 100,
        "hardware_shutoff_acknowledged": True,
        "maintenance_max_duration": max_duration,
        "maintenance_confirmation_interval": confirmation_interval,
        "calibration_settle_seconds": 0,
    }
    if measured:
        data.update(
            {
                "water_meter": "sensor.water_meter",
                "meter_type": "cumulative",
                "meter_entity": "sensor.water_meter",
                "leak_monitoring": False,
            }
        )
        hass.states.async_set(
            "sensor.water_meter",
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
        )
        if with_flow:
            data["flow_sensor"] = "sensor.flow"
            hass.states.async_set(
                "sensor.flow",
                "10",
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
            )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data=data,
        unique_id="installation-safety-modes",
        version=2,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 60,
                "min_flow": 5,
                "max_flow": 15,
                "flow_grace_seconds": 0,
                "area_m2": 10,
                "application_efficiency": 0.5,
                "maximum_deficit_mm": 50,
                "minimum_effective_liters": 0.1,
                "automation_enabled": True,
                "watering_mode": "demand",
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
    assert entry.runtime_data.manager._stored_state.installation_safety_lock is None, (
        entry.runtime_data.manager._stored_state.installation_safety_lock
    )
    operations.clear()
    return entry, zone, operations


async def test_installation_safety_lock_marks_every_zone_locked(
    hass: HomeAssistant,
) -> None:
    """Publish a global safety lock as the effective status of every zone."""
    entry, zone, _ = await _setup(hass)
    manager = entry.runtime_data.manager
    occurred_at = "2026-07-23T05:58:00+00:00"
    manager._stored_state = replace(
        manager._stored_state,
        installation_safety_lock="switch.lawn opened unexpectedly",
        installation_safety_lock_at=occurred_at,
    )

    manager._publish(status="safety_lock", active_zone_id=None)
    await hass.async_block_till_done()

    assert entry.runtime_data.coordinator.data.zone_status[zone.unique_id] == "safety_lock"
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-safety-modes_safety_lock"
    )
    assert entity_id is not None
    lock_state = hass.states.get(entity_id)
    assert lock_state is not None
    assert lock_state.attributes["reason"] == "switch.lawn opened unexpectedly"
    assert lock_state.attributes["occurred_at"] == occurred_at


async def test_winter_lock_closes_persists_and_blocks_every_watering_path(
    hass: HomeAssistant,
) -> None:
    """Keep winter protection through restart and block manual, automatic, and tests."""
    entry, zone, operations = await _setup(hass)
    timeline: list[str] = []

    @callback
    def record_winter_event(event: Event) -> None:
        if event.data["event_type"] == "winter_lock_activated":
            timeline.append("event")

    unsubscribe = hass.bus.async_listen(EVENT_IRRIGATION_MANAGER, record_winter_event)

    async def record_turn_off(call) -> None:
        timeline.append("close")
        operations.append(("off", call.data["entity_id"]))
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", record_turn_off)

    await hass.services.async_call(
        DOMAIN,
        "set_winter_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.winter_lock is True
    assert ("off", "switch.lawn") in operations
    assert timeline.index("close") < timeline.index("event")

    hass.states.async_set("switch.lawn", STATE_ON)
    operations.clear()
    timeline.clear()
    await hass.services.async_call(
        DOMAIN,
        "set_winter_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    assert hass.states.get("switch.lawn").state == STATE_OFF
    assert ("off", "switch.lawn") in operations
    assert timeline.index("close") < timeline.index("event")
    unsubscribe()
    assert entry.runtime_data.manager._stored_state.installation_safety_lock is not None
    await hass.services.async_call(
        DOMAIN,
        "clear_winter_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    await entry.runtime_data.manager.async_reset_safety_lock()
    await hass.services.async_call(
        DOMAIN,
        "set_winter_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    with pytest.raises(HomeAssistantError, match="winter lock"):
        await entry.runtime_data.manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )
    with pytest.raises(HomeAssistantError, match="winter lock"):
        await entry.runtime_data.manager.async_start_maintenance_test(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=0.1,
        )
    report = await entry.runtime_data.manager.async_plan_automatic(dry_run=True)
    assert report["would_create_request_ids"] == []

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-safety-modes_winter_lock"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "clear_winter_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    assert not (await IrrigationStore(hass, entry.entry_id).async_load()).winter_lock


async def test_lost_deadman_confirmation_closes_valve_and_clears_maintenance(
    hass: HomeAssistant,
) -> None:
    """Fail closed when a supervising client stops confirming the test."""
    entry, zone, operations = await _setup(hass, confirmation_interval=0.02)

    response = await hass.services.async_call(
        DOMAIN,
        "start_maintenance_test",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zone.subentry_id,
            "duration": 0.5,
            "bypass_checks": ["flow"],
        },
        blocking=True,
        return_response=True,
    )
    assert response["test_id"]
    await _wait_until(lambda: ("on", "switch.lawn") in operations)
    with pytest.raises(HomeAssistantError, match="maintenance test"):
        await entry.runtime_data.manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=0.1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )
    await _wait_until(lambda: entry.runtime_data.manager._stored_state.maintenance_test is None)

    assert hass.states.get("switch.lawn").state == STATE_OFF


async def test_deadman_confirmation_is_capped_and_fixed_expiry_is_enforced(
    hass: HomeAssistant,
) -> None:
    """Never let confirmations extend the fixed maintenance-mode expiry."""
    entry, zone, operations = await _setup(
        hass,
        confirmation_interval=1,
        max_duration=0.08,
    )
    ended_reasons: list[str] = []

    @callback
    def record_end(event: Event) -> None:
        if event.data["event_type"] == "maintenance_ended":
            ended_reasons.append(event.data["reason"])

    unsubscribe = hass.bus.async_listen(EVENT_IRRIGATION_MANAGER, record_end)
    response = await entry.runtime_data.manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.08,
        bypass_checks=("flow",),
    )
    confirmation = await entry.runtime_data.manager.async_confirm_maintenance_test(
        test_id=str(response["test_id"])
    )
    test = entry.runtime_data.manager._stored_state.maintenance_test
    assert test is not None
    assert datetime.fromisoformat(str(confirmation["confirmation_deadline"])) <= (
        datetime.fromisoformat(test.expires_at)
    )

    await _wait_until(lambda: entry.runtime_data.manager._stored_state.maintenance_test is None)
    await hass.async_block_till_done()

    assert hass.states.get("switch.lawn").state == STATE_OFF
    assert ("off", "switch.lawn") in operations
    assert "hard_timeout" in ended_reasons
    unsubscribe()


async def test_restart_closes_and_clears_persisted_maintenance_test(
    hass: HomeAssistant,
) -> None:
    """Never resume a supervised test or leave its valve open after restart recovery."""
    entry, zone, operations = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    now = datetime.now(UTC)
    test = MaintenanceTestState(
        test_id="interrupted-test",
        kind="maintenance",
        zone_id="zone-lawn",
        zone_subentry_id=zone.subentry_id,
        started_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        confirmation_deadline=(now + timedelta(seconds=10)).isoformat(),
        bypass_checks=("flow",),
    )
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(
            maintenance_test=test,
            active_execution=ActiveExecutionState(
                zone_id="zone-lawn",
                zone_valve="switch.lawn",
                main_valve=None,
                meter_raw_baseline_liters=None,
                prepared_at=test.started_at,
                watering_started_at=(now - timedelta(seconds=1)).isoformat(),
                requested_duration_seconds=60,
                estimated_flow_l_min=60,
                balance_area_m2=10,
                balance_application_efficiency=0.5,
                balance_maximum_deficit_mm=50,
                balance_minimum_effective_liters=0.1,
            ),
            zone_deficit_mm={"zone-lawn": 10},
        )
    )
    hass.states.async_set("switch.lawn", STATE_ON)
    operations.clear()

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.maintenance_test is None
    assert stored.active_execution is None
    assert stored.zone_totals_liters["zone-lawn"] > 0
    assert stored.zone_deficit_mm["zone-lawn"] < 10
    assert hass.states.get("switch.lawn").state == STATE_OFF
    assert ("off", "switch.lawn") in operations
    credited_total = stored.zone_totals_liters["zone-lawn"]
    credited_deficit = stored.zone_deficit_mm["zone-lawn"]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    restarted = await IrrigationStore(hass, entry.entry_id).async_load()
    assert restarted.zone_totals_liters["zone-lawn"] == credited_total
    assert restarted.zone_deficit_mm["zone-lawn"] == credited_deficit


async def test_emergency_stop_cancels_supervised_test_and_remains_locked(
    hass: HomeAssistant,
) -> None:
    """Never let maintenance supervision weaken emergency stop."""
    entry, zone, operations = await _setup(hass, confirmation_interval=1)
    await entry.runtime_data.manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.5,
        bypass_checks=("flow",),
    )
    await _wait_until(lambda: ("on", "switch.lawn") in operations)

    await entry.runtime_data.manager.async_emergency_stop()

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.emergency_stop is True
    assert stored.maintenance_test is None
    assert stored.active_execution is None
    assert hass.states.get("switch.lawn").state == STATE_OFF


async def test_calibration_books_water_and_requires_separate_acceptance(
    hass: HomeAssistant,
) -> None:
    """Keep measured calibration output as a proposal until explicitly accepted."""
    entry, zone, _ = await _setup(hass, confirmation_interval=1, measured=True)

    manager = entry.runtime_data.manager
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        kind="calibration",
    )
    task = manager._maintenance_task
    assert task is not None
    result = await task
    assert result.safety_violation is None
    assert manager._maintenance_flow_samples
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    proposal = stored.calibration_proposal
    assert proposal is not None
    assert proposal.status == "pending"
    assert proposal.delivered_liters == pytest.approx(0.003)
    assert 0 < proposal.duration_seconds < 0.02
    assert proposal.average_flow_l_min == pytest.approx(
        proposal.delivered_liters * 60 / proposal.duration_seconds
    )
    assert stored.zone_totals_liters["zone-lawn"] == pytest.approx(0.003)
    assert entry.subentries[zone.subentry_id].data["min_flow"] == 5
    assert entry.subentries[zone.subentry_id].data["max_flow"] == 15

    await entry.runtime_data.manager.async_resolve_calibration(
        proposal_id=proposal.proposal_id,
        resolution="accept",
    )
    await hass.async_block_till_done()

    assert entry.subentries[zone.subentry_id].data["min_flow"] == pytest.approx(
        proposal.average_flow_l_min * 0.8
    )
    assert entry.subentries[zone.subentry_id].data["max_flow"] == pytest.approx(
        proposal.average_flow_l_min * 1.2
    )


async def test_calibration_derives_flow_from_cumulative_meter_without_flow_sensor(
    hass: HomeAssistant,
) -> None:
    """Calibrate from delivered volume and duration without a direct flow sensor."""
    entry, zone, operations = await _setup(hass, measured=True, with_flow=False)
    manager = entry.runtime_data.manager
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        kind="calibration",
    )
    task = manager._maintenance_task
    assert task is not None
    result = await task

    assert result.safety_violation is None
    assert ("on", "switch.lawn") in operations
    assert manager._stored_state.installation_safety_lock is None
    assert manager._stored_state.maintenance_test is None
    proposal = manager._stored_state.calibration_proposal
    assert proposal is not None
    assert proposal.average_flow_l_min == pytest.approx(
        proposal.delivered_liters * 60 / proposal.duration_seconds
    )


async def test_calibration_without_meter_progress_locks_installation(
    hass: HomeAssistant,
) -> None:
    """Fail safely when a supervised calibration observes no physical water response."""
    entry, zone, _ = await _setup(
        hass,
        measured=True,
        with_flow=False,
        measured_liters=0,
    )
    manager = entry.runtime_data.manager
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        kind="calibration",
    )
    task = manager._maintenance_task
    assert task is not None

    result = await task

    assert result.safety_scope == "zone"
    assert "no cumulative meter progress" in (result.safety_violation or "").lower()
    assert manager._stored_state.zone_safety_locks == {}
    assert (
        "no cumulative meter progress"
        in (manager._stored_state.installation_safety_lock or "").lower()
    )
    assert manager._stored_state.calibration_proposal is None


async def test_calibration_accept_rejects_reconfigured_zone(hass: HomeAssistant) -> None:
    """Reject a proposal whose valve or relevant zone settings changed after measuring."""
    entry, zone, _ = await _setup(hass, confirmation_interval=1, measured=True)
    manager = entry.runtime_data.manager
    await manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        kind="calibration",
    )
    task = manager._maintenance_task
    assert task is not None
    await task
    proposal = manager._stored_state.calibration_proposal
    assert proposal is not None

    live_subentry = entry.subentries[zone.subentry_id]
    hass.config_entries.async_update_subentry(
        entry,
        live_subentry,
        data={**live_subentry.data, "max_flow": 16},
    )

    with pytest.raises(HomeAssistantError, match="changed after calibration"):
        await manager.async_resolve_calibration(
            proposal_id=proposal.proposal_id,
            resolution="accept",
        )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.calibration_proposal is not None
    assert stored.calibration_proposal.status == "pending"
    assert entry.subentries[zone.subentry_id].data["max_flow"] == 16
