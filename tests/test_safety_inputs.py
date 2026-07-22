"""Qualification tests for actuator, external, and wind safety inputs."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.irrigation_manager.const import EVENT_IRRIGATION_MANAGER
from custom_components.irrigation_manager.models import ActiveExecutionState
from custom_components.irrigation_manager.storage import IrrigationStore

from .irrigation_plant import FakeHaIrrigationPlant


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(2):
        while not predicate():  # noqa: ASYNC110 - state changes have no dedicated test seam
            await asyncio.sleep(0.001)


async def test_own_command_feedback_transition_does_not_trigger_false_lock(
    hass: HomeAssistant,
) -> None:
    """Record command intent before a synchronous separate-feedback state event."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set("binary_sensor.lawn_feedback", STATE_OFF)

    async def turn_on(call) -> None:
        entity_id = str(call.data["entity_id"])
        await plant.open(entity_id)
        if entity_id == "switch.lawn":
            hass.states.async_set("binary_sensor.lawn_feedback", STATE_ON)

    async def turn_off(call) -> None:
        entity_id = str(call.data["entity_id"])
        await plant.close(entity_id)
        if entity_id == "switch.lawn":
            hass.states.async_set("binary_sensor.lawn_feedback", STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    entry = await plant.setup_entry(
        with_flow=False,
        installation_data={"actuator_transition_grace_seconds": 0.5},
        zone_data=[{"zone_valve_feedback": "binary_sensor.lawn_feedback"}],
    )
    zone = next(iter(entry.subentries.values()))
    manager = entry.runtime_data.manager

    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert stored.zone_safety_locks == {}
    assert ("open", "switch.lawn") in [
        (operation, entity) for _, operation, entity in plant.operations
    ]


async def test_unavailable_separate_feedback_at_startup_closes_and_locks(
    hass: HomeAssistant,
) -> None:
    """Keep the integration loaded but safety-locked after startup feedback failure."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set("binary_sensor.lawn_feedback", STATE_UNAVAILABLE)
    entry = await plant.setup_entry(
        installation_data={"actuator_transition_grace_seconds": 0.01},
        zone_data=[{"zone_valve_feedback": "binary_sensor.lawn_feedback"}],
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is not None
    assert ("close", "switch.lawn") in [
        (operation, entity) for _, operation, entity in plant.operations
    ]


async def test_feedback_loss_during_operation_stops_and_locks_zone(
    hass: HomeAssistant,
) -> None:
    """Continuously supervise the separate feedback after command confirmation."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set("binary_sensor.lawn_feedback", STATE_OFF)

    async def turn_on(call) -> None:
        entity_id = str(call.data["entity_id"])
        await plant.open(entity_id)
        if entity_id == "switch.lawn":
            hass.states.async_set("binary_sensor.lawn_feedback", STATE_ON)

    async def turn_off(call) -> None:
        entity_id = str(call.data["entity_id"])
        await plant.close(entity_id)
        if entity_id == "switch.lawn":
            hass.states.async_set("binary_sensor.lawn_feedback", STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    entry = await plant.setup_entry(
        with_flow=False,
        installation_data={"actuator_transition_grace_seconds": 0.02},
        zone_data=[{"zone_valve_feedback": "binary_sensor.lawn_feedback"}],
    )
    zone = next(iter(entry.subentries.values()))
    await entry.runtime_data.manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.5,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await _wait_until(lambda: "switch.lawn" in plant.open_valves)

    hass.states.async_set("binary_sensor.lawn_feedback", STATE_UNAVAILABLE)
    await _wait_until(lambda: not plant.open_valves)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert "qualification-zone-1" in stored.zone_safety_locks
    assert stored.installation_safety_lock is None


async def test_zone_external_permit_change_stops_and_locks_only_zone(
    hass: HomeAssistant,
) -> None:
    """Apply a zonal permit transition immediately to the owning active operation."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set("binary_sensor.lawn_permit", STATE_ON)
    entry = await plant.setup_entry(
        zone_data=[{"external_permit": "binary_sensor.lawn_permit"}],
    )
    zone = next(iter(entry.subentries.values()))
    response = await entry.runtime_data.manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.5,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    assert response["request_id"]
    await _wait_until(lambda: "switch.lawn" in plant.open_valves)

    hass.states.async_set("binary_sensor.lawn_permit", STATE_OFF)
    await _wait_until(lambda: not plant.open_valves)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert "qualification-zone-1" in stored.zone_safety_locks


async def test_delayed_external_event_cannot_lock_or_cancel_the_next_operation(
    hass: HomeAssistant,
) -> None:
    """Re-evaluate the current operation only after acquiring the command lock."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.lawn": 10, "switch.beds": 10},
    )
    hass.states.async_set("binary_sensor.lawn_permit", STATE_OFF)
    entry = await plant.setup_entry(
        zone_data=[
            {"external_permit": "binary_sensor.lawn_permit"},
            {},
        ],
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC).isoformat()
    first_operation = ActiveExecutionState(
        zone_id="qualification-zone-1",
        zone_valve="switch.lawn",
        main_valve=plant.main_valve,
        meter_raw_baseline_liters=None,
        prepared_at=now,
        watering_started_at=now,
        requested_duration_seconds=60,
        estimated_flow_l_min=10,
        execution_id="operation-1",
    )
    second_operation = replace(
        first_operation,
        zone_id="qualification-zone-2",
        zone_valve="switch.beds",
        execution_id="operation-2",
    )
    second_task = asyncio.create_task(asyncio.Event().wait())
    manager._active_task = second_task

    try:
        async with manager._command_lock:
            manager._stored_state = replace(
                manager._stored_state,
                active_execution=first_operation,
            )
            delayed_event = asyncio.create_task(manager._async_apply_external_interlocks())
            await asyncio.sleep(0)
            manager._stored_state = replace(
                manager._stored_state,
                active_execution=second_operation,
            )

        assert await delayed_event is False
        assert not second_task.done()
        assert manager._stored_state.installation_safety_lock is None
        assert manager._stored_state.zone_safety_locks == {}
        assert manager._stored_state.active_execution == second_operation
    finally:
        second_task.cancel()
        await asyncio.gather(second_task, return_exceptions=True)
        manager._active_task = None
        manager._stored_state = replace(manager._stored_state, active_execution=None)


async def test_strong_wind_blocks_automatic_and_configured_manual_irrigation(
    hass: HomeAssistant,
) -> None:
    """Apply the zonal threshold to automatic work and the selected manual policy."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set(
        "sensor.lawn_wind",
        "8",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfSpeed.METERS_PER_SECOND},
    )
    entry = await plant.setup_entry(
        zone_data=[
            {
                "wind_interlock_entity": "sensor.lawn_wind",
                "wind_interlock_threshold": 5,
                "wind_manual_policy": "block",
                "automation_enabled": True,
                "agronomic_values_confirmed": True,
                "watering_windows": ["00:00-23:59"],
            }
        ],
    )
    zone = next(iter(entry.subentries.values()))

    report = await entry.runtime_data.manager.async_plan_automatic(dry_run=True)
    assert report["zones"][0]["reason"] == "safety_blocked"
    with pytest.raises(HomeAssistantError, match="Wind interlock"):
        await entry.runtime_data.manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=0.01,
            amount_liters=None,
            hard_time_limit_seconds=None,
        )


@pytest.mark.parametrize(
    ("unit", "below_threshold", "above_threshold"),
    [
        (UnitOfSpeed.KILOMETERS_PER_HOUR, 25, 40),
        (UnitOfSpeed.MILES_PER_HOUR, 15, 25),
    ],
)
async def test_wind_sensor_native_units_are_compared_to_canonical_mps_threshold(
    hass: HomeAssistant,
    unit: UnitOfSpeed,
    below_threshold: float,
    above_threshold: float,
) -> None:
    """Convert km/h and mph sensor values before comparing with the m/s threshold."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set(
        "sensor.lawn_wind",
        str(below_threshold),
        {ATTR_UNIT_OF_MEASUREMENT: unit},
    )
    entry = await plant.setup_entry(
        zone_data=[
            {
                "wind_interlock_entity": "sensor.lawn_wind",
                "wind_interlock_threshold": 10,
            }
        ],
    )
    zone = next(iter(entry.subentries.values()))
    manager = entry.runtime_data.manager

    assert not manager._wind_blocks(zone.data, source="automatic")
    hass.states.async_set(
        "sensor.lawn_wind",
        str(above_threshold),
        {ATTR_UNIT_OF_MEASUREMENT: unit},
    )
    assert manager._wind_blocks(zone.data, source="automatic")


async def test_strong_wind_change_stops_relevant_manual_operation(
    hass: HomeAssistant,
) -> None:
    """Report wind as the active stop reason even when manual rain override applies."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    attributes = {ATTR_UNIT_OF_MEASUREMENT: UnitOfSpeed.METERS_PER_SECOND}
    hass.states.async_set("sensor.lawn_wind", "2", attributes)
    hass.states.async_set("sensor.rain", "1")
    events = []
    hass.bus.async_listen(EVENT_IRRIGATION_MANAGER, events.append)
    entry = await plant.setup_entry(
        with_flow=False,
        installation_data={
            "rain_stop_entity": "sensor.rain",
            "rain_stop_threshold": 0.1,
        },
        zone_data=[
            {
                "wind_interlock_entity": "sensor.lawn_wind",
                "wind_interlock_threshold": 5,
                "wind_manual_policy": "block",
            }
        ],
    )
    zone = next(iter(entry.subentries.values()))
    await entry.runtime_data.manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.5,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await _wait_until(lambda: "switch.lawn" in plant.open_valves)

    hass.states.async_set("sensor.lawn_wind", "8", attributes)
    await _wait_until(lambda: not plant.open_valves)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert stored.zone_safety_locks == {}
    assert any(
        event.data["event_type"] == "weather_interlock_activated"
        and event.data["reason"] == "wind"
        and event.data["target"] == {"type": "zone", "id": "qualification-zone-1"}
        for event in events
    )


async def test_supervised_overrides_are_individual_and_test_scoped(
    hass: HomeAssistant,
) -> None:
    """Bypass selected observations only until the one supervised test finishes."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.lawn": 10})
    hass.states.async_set("binary_sensor.lawn_feedback", STATE_OFF)
    hass.states.async_set("binary_sensor.lawn_permit", STATE_ON)
    entry = await plant.setup_entry(
        installation_data={"maintenance_confirmation_interval": 1},
        zone_data=[
            {
                "zone_valve_feedback": "binary_sensor.lawn_feedback",
                "external_permit": "binary_sensor.lawn_permit",
            }
        ],
    )
    zone = next(iter(entry.subentries.values()))
    hass.states.async_set("binary_sensor.lawn_feedback", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.lawn_permit", STATE_OFF)

    await entry.runtime_data.manager.async_start_maintenance_test(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.02,
        bypass_checks=("feedback", "flow", "weather", "external"),
    )
    task = entry.runtime_data.manager._maintenance_task
    assert task is not None
    await task
    assert entry.runtime_data.manager._stored_state.maintenance_test is None

    with pytest.raises(HomeAssistantError, match="external safety preflight"):
        await entry.runtime_data.manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=0.01,
            amount_liters=None,
            hard_time_limit_seconds=None,
        )
