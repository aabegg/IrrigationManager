"""Persistent manual request tests through Home Assistant's public seams."""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_OFF, STATE_ON, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.executor import ExecutionResult
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
)
from custom_components.irrigation_manager.storage import IrrigationStore


async def _wait_until(predicate: Callable[[], bool]) -> None:
    async with asyncio.timeout(2):
        while not predicate():  # noqa: ASYNC110 - persisted state has no event seam
            await asyncio.sleep(0.001)


async def _setup_installation(
    hass: HomeAssistant,
    *,
    zone_specs: tuple[tuple[str, str, float, float], ...],
) -> tuple[MockConfigEntry, list[ConfigSubentry], list[tuple[str, str]]]:
    operations: list[tuple[str, str]] = []

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        assert not any(
            state.state == STATE_ON
            for candidate in zone_specs
            if (state := hass.states.get(candidate[1])) is not None and candidate[1] != entity_id
        )
        operations.append(("on", entity_id))
        hass.states.async_set(entity_id, STATE_ON)

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("off", entity_id))
        hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-requests",
    )
    entry.add_to_hass(hass)
    subentries: list[ConfigSubentry] = []
    for index, (name, valve, max_dose, soak) in enumerate(zone_specs, start=1):
        hass.states.async_set(valve, STATE_OFF)
        subentry = ConfigSubentry(
            data=MappingProxyType(
                {
                    "name": name,
                    "zone_valve": valve,
                    "default_duration": 60,
                    "max_dose_duration": max_dose,
                    "soak_duration": soak,
                }
            ),
            subentry_id=f"subentry-{index}",
            subentry_type="zone",
            title=name,
            unique_id=f"zone-{index}",
        )
        hass.config_entries.async_add_subentry(entry, subentry)
        subentries.append(subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    operations.clear()
    return entry, subentries, operations


async def test_split_request_persists_one_execution_across_soak_doses(
    hass: HomeAssistant,
) -> None:
    """Run a split target as one execution and expose its durable progress."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 0.01, 0.01),),
    )

    response = await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 0.025,
        },
        blocking=True,
        return_response=True,
    )

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    request = next(
        item for item in state.manual_requests if item.request_id == response["request_id"]
    )
    execution = next(
        item for item in state.irrigation_executions if item.execution_id == request.execution_id
    )
    assert request.status == "completed"
    assert request.remaining_value == 0
    assert execution.status == "completed"
    assert execution.dose_number == 3
    assert [operation for operation in operations if operation[0] == "on"] == [
        ("on", "switch.lawn"),
        ("on", "switch.lawn"),
        ("on", "switch.lawn"),
    ]


async def test_options_update_during_watering_reloads_only_after_complete_idle(
    hass: HomeAssistant,
) -> None:
    """Persist expert edits immediately without replacing an active runtime snapshot."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 60, 0),),
    )
    hass.states.async_set("switch.new_lawn", STATE_OFF)
    old_manager = entry.runtime_data.manager
    response = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 60,
        },
        blocking=True,
        return_response=True,
    )
    await _wait_until(lambda: ("on", "switch.lawn") in operations)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "zone"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"zone_subentry_id": zones[0].subentry_id}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "New lawn",
            "zone_valve": "switch.new_lawn",
            "default_duration": 30,
            "max_dose_duration": 30,
            "area_m2": 20,
            "application_efficiency": 0.6,
            "maximum_deficit_mm": 25,
            "minimum_effective_liters": 7,
        },
    )

    assert result["type"].value == "create_entry"
    assert entry.subentries[zones[0].subentry_id].data["zone_valve"] == "switch.new_lawn"
    assert entry.runtime_data.manager is old_manager
    assert old_manager._zone_valves() == ["switch.lawn"]
    stored_during_execution = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored_during_execution.active_execution is not None
    assert stored_during_execution.active_execution.zone_valve == "switch.lawn"
    assert hass.states.get("switch.lawn").state == STATE_ON
    assert ("on", "switch.new_lawn") not in operations

    await hass.services.async_call(
        DOMAIN,
        "cancel_request",
        {
            "config_entry_id": entry.entry_id,
            "request_id": response["request_id"],
        },
        blocking=True,
    )
    await _wait_until(lambda: entry.runtime_data.manager is not old_manager)

    new_manager = entry.runtime_data.manager
    stored_after_reload = await IrrigationStore(hass, entry.entry_id).async_load()
    request = next(
        item
        for item in stored_after_reload.manual_requests
        if item.request_id == response["request_id"]
    )
    assert request.status == "cancelled"
    assert request.zone_valve == "switch.lawn"
    assert new_manager._zone_valves() == ["switch.new_lawn"]
    assert new_manager._zone_configs[0].data["area_m2"] == 20
    assert new_manager._zone_configs[0].data["application_efficiency"] == 0.6
    assert new_manager._zone_configs[0].data["maximum_deficit_mm"] == 25
    assert new_manager._zone_configs[0].data["minimum_effective_liters"] == 7
    assert ("off", "switch.lawn") in operations
    assert ("on", "switch.new_lawn") not in operations


async def test_other_zone_runs_during_soak_and_soaking_request_can_be_cancelled(
    hass: HomeAssistant,
) -> None:
    """Release hydraulics during soak and cancel the selected open request."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(
            ("Lawn", "switch.lawn", 0.01, 0.2),
            ("Beds", "switch.beds", 1, 0),
        ),
    )
    first = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 0.03,
        },
        blocking=True,
        return_response=True,
    )
    store = IrrigationStore(hass, entry.entry_id)
    await _wait_until(
        lambda: any(
            item.request_id == first["request_id"] and item.status == "soaking"
            for item in entry.runtime_data.manager._stored_state.manual_requests
        )
    )

    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[1].subentry_id,
            "duration": 0.005,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "cancel_request",
        {"config_entry_id": entry.entry_id, "request_id": first["request_id"]},
        blocking=True,
    )

    state = await store.async_load()
    first_request = next(
        item for item in state.manual_requests if item.request_id == first["request_id"]
    )
    assert first_request.status == "cancelled"
    assert first_request.remaining_value > 0
    assert [operation for operation in operations if operation[0] == "on"] == [
        ("on", "switch.lawn"),
        ("on", "switch.beds"),
    ]


async def test_pause_and_resume_preserve_the_remaining_target(hass: HomeAssistant) -> None:
    """Close an active dose on pause and continue only its persisted remainder."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 1, 0),),
    )
    response = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 0.05,
        },
        blocking=True,
        return_response=True,
    )
    request_id = response["request_id"]
    await _wait_until(
        lambda: (state := hass.states.get("switch.lawn")) is not None and state.state == STATE_ON
    )

    await hass.services.async_call(
        DOMAIN,
        "pause_request",
        {"config_entry_id": entry.entry_id, "request_id": request_id},
        blocking=True,
    )
    await _wait_until(
        lambda: entry.runtime_data.manager._stored_state.manual_requests[0].status == "paused"
    )
    paused_remaining = entry.runtime_data.manager._stored_state.manual_requests[0].remaining_value
    assert 0 < paused_remaining < 0.05
    assert hass.states.get("switch.lawn").state == STATE_OFF

    await hass.services.async_call(
        DOMAIN,
        "resume_request",
        {"config_entry_id": entry.entry_id, "request_id": request_id},
        blocking=True,
    )
    await _wait_until(
        lambda: entry.runtime_data.manager._stored_state.manual_requests[0].status == "completed"
    )

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert state.manual_requests[0].remaining_value == 0
    assert [operation for operation in operations if operation[0] == "on"] == [
        ("on", "switch.lawn"),
        ("on", "switch.lawn"),
    ]


async def test_restart_interrupts_active_dose_and_replans_unexpired_remainder(
    hass: HomeAssistant,
) -> None:
    """Account the interrupted dose, retain its history, and safely create a new execution."""
    operations: list[str] = []

    async def turn_on(call) -> None:
        operations.append(f"on:{call.data['entity_id']}")
        hass.states.async_set(call.data["entity_id"], STATE_ON)

    async def turn_off(call) -> None:
        operations.append(f"off:{call.data['entity_id']}")
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-restart",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 60,
                "max_dose_duration": 0.01,
                "soak_duration": 0,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="request-restart",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="subentry-1",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=0.03,
        remaining_value=0.03,
        created_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        status="executing",
        execution_id="execution-interrupted",
        max_dose_value=0.01,
    )
    execution = IrrigationExecutionState(
        execution_id="execution-interrupted",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type="duration",
        target_value=request.target_value,
        remaining_value=request.remaining_value,
        status="watering",
        created_at=request.created_at,
        dose_number=1,
    )
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(
            manual_requests=(request,),
            irrigation_executions=(execution,),
            next_request_sequence=2,
            active_execution=ActiveExecutionState(
                zone_id="zone-1",
                zone_valve="switch.lawn",
                main_valve=None,
                meter_raw_baseline_liters=None,
                prepared_at=(now - timedelta(seconds=0.01)).isoformat(),
                watering_started_at=(now - timedelta(seconds=0.01)).isoformat(),
                requested_duration_seconds=0.01,
                estimated_flow_l_min=None,
                request_id=request.request_id,
                execution_id=execution.execution_id,
                dose_number=1,
                dose_target_value=0.01,
            ),
        )
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await _wait_until(
        lambda: entry.runtime_data.manager._stored_state.manual_requests[0].status == "completed"
    )

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert state.manual_requests[0].status == "completed"
    assert [item.status for item in state.irrigation_executions] == [
        "interrupted",
        "completed",
    ]
    assert all("switch.lawn" in operation for operation in operations)


async def test_restart_recovery_that_satisfies_remainder_completes_without_new_dose(
    hass: HomeAssistant,
) -> None:
    """Complete an execution when recovered delivery consumes its final remainder."""
    opened: list[str] = []

    async def turn_on(call) -> None:
        opened.append(call.data["entity_id"])
        hass.states.async_set(call.data["entity_id"], STATE_ON)

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-recovery-complete",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {"name": "Lawn", "zone_valve": "switch.lawn", "default_duration": 60}
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="request-recovery-complete",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id=subentry.subentry_id,
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=0.001,
        created_at=(now - timedelta(seconds=2)).isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        status="executing",
        execution_id="execution-recovery-complete",
    )
    execution = IrrigationExecutionState(
        execution_id="execution-recovery-complete",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type=request.target_type,
        target_value=request.target_value,
        remaining_value=request.remaining_value,
        status="watering",
        created_at=request.created_at,
        dose_number=1,
    )
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(
            manual_requests=(request,),
            irrigation_executions=(execution,),
            next_request_sequence=2,
            active_execution=ActiveExecutionState(
                zone_id=request.zone_id,
                zone_valve=request.zone_valve,
                main_valve=None,
                meter_raw_baseline_liters=None,
                prepared_at=(now - timedelta(seconds=1)).isoformat(),
                watering_started_at=(now - timedelta(seconds=1)).isoformat(),
                requested_duration_seconds=1,
                estimated_flow_l_min=None,
                request_id=request.request_id,
                execution_id=execution.execution_id,
                dose_number=1,
                dose_target_value=1,
            ),
        )
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await asyncio.sleep(0.02)

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert state.manual_requests[0].status == "completed"
    assert state.manual_requests[0].remaining_value == 0
    assert state.manual_requests[0].execution_id == execution.execution_id
    assert state.irrigation_executions[0].status == "completed"
    assert state.irrigation_executions[0].remaining_value == 0
    assert state.irrigation_executions[0].result == "target_reached_during_recovery"
    assert state.irrigation_executions[0].dose_number == 1
    assert opened == []


async def test_expired_persisted_request_never_opens_its_zone(hass: HomeAssistant) -> None:
    """Expire a queued order during startup validation without touching hydraulics."""
    opened = False

    async def turn_on(call) -> None:
        nonlocal opened
        opened = True

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-expiry",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {"name": "Lawn", "zone_valve": "switch.lawn", "default_duration": 60}
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="request-expired",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id="subentry-1",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at=(now - timedelta(minutes=2)).isoformat(),
        expires_at=(now - timedelta(minutes=1)).isoformat(),
    )
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(manual_requests=(request,), next_request_sequence=2)
    )

    assert await hass.config_entries.async_setup(entry.entry_id)

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert state.manual_requests[0].status == "expired"
    assert opened is False


async def test_execution_hard_runtime_is_consumed_across_split_volume_doses(
    hass: HomeAssistant,
) -> None:
    """Give each split dose only the execution-wide runtime still unconsumed."""
    hard_limits_at_open: list[float] = []

    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_ON)
        stored = await IrrigationStore(hass, entry.entry_id).async_load()
        assert stored.active_execution is not None
        assert stored.active_execution.hard_time_limit_seconds is not None
        hard_limits_at_open.append(stored.active_execution.hard_time_limit_seconds)

        async def advance_meter() -> None:
            await asyncio.sleep(0.01)
            current = hass.states.get("sensor.water_meter")
            assert current is not None
            hass.states.async_set(
                "sensor.water_meter",
                str(float(current.state) + 1),
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
            )

        hass.async_create_task(advance_meter(), "Advance irrigation test meter")

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.water_meter",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation", "water_meter": "sensor.water_meter"},
        unique_id="installation-runtime-budget",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 60,
                "max_dose_amount": 1,
                "soak_duration": 0,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "amount": 2,
            "hard_time_limit": 2.5,
        },
        blocking=True,
    )

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    execution = state.irrigation_executions[0]
    assert execution.status == "completed"
    assert execution.delivered_duration_seconds == pytest.approx(2, abs=0.2)
    assert hard_limits_at_open[0] == 2.5
    assert hard_limits_at_open[1] == pytest.approx(
        2.5 - execution.delivered_duration_seconds / 2,
        abs=0.2,
    )
    assert hard_limits_at_open[1] < hard_limits_at_open[0]


async def test_dose_accounting_and_lifecycle_are_one_durable_transition(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never persist accounted water while leaving its request marked executing."""
    entry, zones, _ = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 10, 0),),
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="request-atomic",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id=zones[0].subentry_id,
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        status="executing",
        execution_id="execution-atomic",
    )
    execution = IrrigationExecutionState(
        execution_id="execution-atomic",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type=request.target_type,
        target_value=1,
        remaining_value=1,
        status="watering",
        created_at=now.isoformat(),
        dose_number=1,
    )
    manager._stored_state = StoredInstallationState(
        manual_requests=(request,),
        irrigation_executions=(execution,),
        active_execution=ActiveExecutionState(
            zone_id="zone-1",
            zone_valve="switch.lawn",
            main_valve=None,
            meter_raw_baseline_liters=None,
            prepared_at=now.isoformat(),
            watering_started_at=now.isoformat(),
            requested_duration_seconds=1,
            estimated_flow_l_min=None,
            request_id=request.request_id,
            execution_id=execution.execution_id,
        ),
    )
    saved_states: list[StoredInstallationState] = []

    async def capture_save(state: StoredInstallationState) -> None:
        saved_states.append(state)

    monkeypatch.setattr(manager._store, "async_save", capture_save)

    await manager._async_finish_dose(
        request.request_id,
        ExecutionResult(
            zone_id="zone-1",
            delivered_liters=3,
            duration_seconds=1,
        ),
    )

    assert len(saved_states) == 1
    saved = saved_states[0]
    assert saved.installation_total_liters == 3
    assert saved.active_execution is None
    assert saved.manual_requests[0].status == "completed"
    assert saved.irrigation_executions[0].status == "completed"


async def test_active_request_stops_at_expiry_and_never_continues(
    hass: HomeAssistant,
) -> None:
    """Treat expiry as an absolute execution opportunity deadline."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 10, 0),),
    )
    response = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 1,
            "expiry": 0.03,
        },
        blocking=True,
        return_response=True,
    )
    await _wait_until(
        lambda: entry.runtime_data.manager._stored_state.manual_requests[0].status == "expired"
    )
    await asyncio.sleep(0.05)

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    request = next(
        item for item in state.manual_requests if item.request_id == response["request_id"]
    )
    assert request.status == "expired"
    assert request.remaining_value > 0
    assert hass.states.get("switch.lawn").state == STATE_OFF
    assert [operation for operation in operations if operation[0] == "on"] == [
        ("on", "switch.lawn")
    ]


async def test_soaking_request_expires_without_another_dose(hass: HomeAssistant) -> None:
    """Do not resume a split execution when its opportunity expires during soak."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 0.01, 1),),
    )
    await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zones[0].subentry_id,
            "duration": 1,
            "expiry": 0.05,
        },
        blocking=True,
        return_response=True,
    )
    await _wait_until(
        lambda: entry.runtime_data.manager._stored_state.manual_requests[0].status == "expired"
    )

    assert [operation for operation in operations if operation[0] == "on"] == [
        ("on", "switch.lawn")
    ]


@pytest.mark.parametrize(
    ("winning_change", "expected_status", "expected_remaining"),
    [
        ("cancel", "cancelled", 1.0),
        ("pause", "paused", 1.0),
        ("replace", "pending", 0.5),
    ],
)
async def test_stale_selected_request_cannot_overwrite_concurrent_change(
    hass: HomeAssistant,
    winning_change: str,
    expected_status: str,
    expected_remaining: float,
) -> None:
    """Let a locked cancel, pause, or replacement win before a stale durable claim."""
    entry, zones, operations = await _setup_installation(
        hass,
        zone_specs=(("Lawn", "switch.lawn", 10, 0),),
    )
    manager = entry.runtime_data.manager
    dispatcher = manager._dispatcher_task
    assert dispatcher is not None
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)
    manager._dispatcher_task = None
    response = await manager.async_start_manual(
        zone_subentry_id=zones[0].subentry_id,
        duration_seconds=1,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    request_id = response["request_id"]
    stale_selected = manager._request(request_id)
    assert stale_selected is not None

    if winning_change == "cancel":
        await manager.async_cancel_request(request_id)
    elif winning_change == "pause":
        await manager.async_pause_request(request_id)
    else:
        async with manager._command_lock:
            current = manager._request(request_id)
            assert current is not None
            replacement = replace(
                current,
                remaining_value=expected_remaining,
                revision=current.revision + 1,
            )
            manager._stored_state = replace(
                manager._stored_state,
                manual_requests=manager._with_request(replacement),
            )
            await manager._store.async_save(manager._stored_state)

    async with manager._command_lock:
        with pytest.raises(HomeAssistantError, match="changed before it could be claimed"):
            await manager._async_prepare_manual(
                manual_request=stale_selected,
                dose_value=1,
                duration_seconds=1,
                amount_liters=None,
                hard_time_limit_seconds=None,
                dose_number=1,
            )

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    current = next(item for item in state.manual_requests if item.request_id == request_id)
    assert current.status == expected_status
    assert current.remaining_value == expected_remaining
    assert current.revision == stale_selected.revision + 1
    assert state.irrigation_executions == ()
    assert state.active_execution is None
    assert operations == []
