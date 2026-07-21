"""Deterministic end-to-end safety qualification scenarios."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.const import STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from custom_components.irrigation_manager.adapters import HomeAssistantMeter
from custom_components.irrigation_manager.executor import (
    ExecutionRequest,
    IrrigationExecutor,
    ValveDidNotOpenError,
)
from custom_components.irrigation_manager.manager import IrrigationManager
from custom_components.irrigation_manager.models import (
    IrrigationExecutionState,
    ManualIrrigationRequest,
    StoredInstallationState,
)
from custom_components.irrigation_manager.storage import IrrigationStore
from tests.irrigation_plant import FakeHaIrrigationPlant


def _executor(plant: FakeHaIrrigationPlant) -> IrrigationExecutor:
    return IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=plant,
        clock=plant.clock,
    )


def _timed_request(
    plant: FakeHaIrrigationPlant, zone_valve: str, seconds: float
) -> ExecutionRequest:
    return ExecutionRequest(
        zone_id=zone_valve.rsplit("_", 1)[-1],
        zone_valve=zone_valve,
        main_valve=plant.main_valve,
        duration_seconds=seconds,
        managed_zone_valves=plant.zone_valves,
        monitor_interval_seconds=1,
    )


async def test_serialized_plant_never_opens_two_zones_and_orders_main_valve(
    hass: HomeAssistant,
) -> None:
    """Serialize concurrent demand and close main around every hydraulic dose."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={
            "switch.zone_lawn": 12,
            "switch.zone_beds": 8,
            "switch.zone_hedge": 6,
            "switch.zone_pots": 4,
            "switch.zone_front": 10,
            "switch.zone_orchard": 14,
        },
    )
    executor = _executor(plant)

    await asyncio.gather(
        *(
            executor.execute(_timed_request(plant, zone_valve, 10))
            for zone_valve in plant.zone_valves
        )
    )

    assert plant.maximum_simultaneous_zones == 1
    operations = [(action, entity_id) for _, action, entity_id in plant.operations]
    opened_zones: set[str] = set()
    for offset in range(0, len(operations), 4):
        opening_main, opening_zone, closing_zone, closing_main = operations[offset : offset + 4]
        assert opening_main == ("open", "switch.irrigation_main")
        assert opening_zone[0] == "open"
        assert closing_zone == ("close", opening_zone[1])
        assert closing_main == ("close", "switch.irrigation_main")
        opened_zones.add(opening_zone[1])
    assert opened_zones == set(plant.zone_valves)
    assert plant.open_valves == set()


async def test_cancellation_race_uses_monotonic_progress_and_closes_every_valve(
    hass: HomeAssistant,
) -> None:
    """Cancel during a dose without attributing requested rather than elapsed time."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 60},
        auto_advance=False,
    )
    task = asyncio.create_task(
        _executor(plant).execute(_timed_request(plant, "switch.zone_lawn", 60))
    )
    await plant.clock.sleeping.wait()
    plant.clock.advance(7)
    plant.clock.jump_wall(timedelta(days=-2))

    task.cancel()
    result = await task

    assert result.stopped
    assert result.duration_seconds == 7
    assert result.delivered_liters == 7
    assert plant.open_valves == set()


@pytest.mark.parametrize("fault", ["open", "close"])
async def test_valve_feedback_faults_fail_closed_when_hardware_is_reachable(
    hass: HomeAssistant,
    fault: str,
) -> None:
    """Detect missing open feedback and report a mechanically stuck close."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    if fault == "open":
        plant.fail_open.add("switch.zone_lawn")
        with pytest.raises(ValveDidNotOpenError):
            await _executor(plant).execute(_timed_request(plant, "switch.zone_lawn", 10))
        assert plant.open_valves == set()
        return

    plant.fail_close.add("switch.zone_lawn")
    result = await _executor(plant).execute(_timed_request(plant, "switch.zone_lawn", 10))
    assert "remained open" in (result.safety_violation or "")
    assert "switch.irrigation_main" not in plant.open_valves
    assert "switch.zone_lawn" in plant.open_valves


@pytest.mark.parametrize(
    ("flow_l_min", "scope", "message"),
    [(2.0, "zone", "below minimum"), (30.0, "installation", "exceeds maximum")],
)
async def test_flow_faults_stop_with_the_required_lock_scope(
    hass: HomeAssistant,
    flow_l_min: float,
    scope: str,
    message: str,
) -> None:
    """Classify blocked supply locally and possible pipe rupture globally."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    plant.flow_override_l_min = flow_l_min

    result = await _executor(plant).execute(
        replace(
            _timed_request(plant, "switch.zone_lawn", 60),
            minimum_flow_l_min=5,
            maximum_flow_l_min=20,
        )
    )

    assert result.safety_scope == scope
    assert message in (result.safety_violation or "")
    assert plant.open_valves == set()


@pytest.mark.parametrize("bad_value", ["nan", "inf", "-1"])
async def test_meter_adapter_rejects_non_finite_and_negative_values(
    hass: HomeAssistant,
    bad_value: str,
) -> None:
    """Never reinterpret invalid meter samples as zero or valid consumption."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    plant.set_meter(bad_value)

    with pytest.raises(HomeAssistantError, match="not plausible"):
        await HomeAssistantMeter(hass, plant.meter_entity_id).read_raw_liters()

    plant.set_meter_unavailable()
    with pytest.raises(HomeAssistantError, match="not available"):
        await HomeAssistantMeter(hass, plant.meter_entity_id).read_raw_liters()


async def test_meter_adapter_rejects_stale_samples(hass: HomeAssistant) -> None:
    """Require a recent cumulative sample before trusting volume control."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    await asyncio.sleep(0.01)

    with pytest.raises(HomeAssistantError, match="stale"):
        await HomeAssistantMeter(
            hass,
            plant.meter_entity_id,
            max_age_seconds=0.001,
        ).read_raw_liters()


@pytest.mark.parametrize(
    ("readings", "message"),
    [([100.0, 99.0, 99.0], "regressed"), ([100.0, 500.0, 500.0], "jump")],
)
async def test_volume_control_rejects_regressing_and_jumping_meter_samples(
    hass: HomeAssistant,
    readings: list[float],
    message: str,
) -> None:
    """Abort volume control when its cumulative source loses plausibility."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    plant.meter_script = readings

    result = await _executor(plant).execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=plant.main_valve,
            amount_liters=10,
            hard_time_limit_seconds=60,
            monitor_interval_seconds=1,
            maximum_flow_l_min=20,
        )
    )

    assert message in (result.safety_violation or "").lower()
    assert not result.target_reached
    assert result.safety_scope == "installation"
    assert plant.open_valves == set()


@pytest.mark.parametrize(
    ("next_raw_liters", "target_reached", "expected_liters", "error_text"),
    [
        (99.0, False, 0.0, "invalid decrease"),
        (3.0, True, 3.0, None),
    ],
)
async def test_executor_uses_production_meter_reset_classification(
    hass: HomeAssistant,
    next_raw_liters: float,
    target_reached: bool,
    expected_liters: float,
    error_text: str | None,
) -> None:
    """Propagate rejected regressions and preserve plausible resets through execution."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    initial_raw_liters = 100.0 if next_raw_liters == 99.0 else 8_490.0
    plant.set_meter(initial_raw_liters)
    plant.clock.on_advance = lambda _seconds: plant.set_meter(next_raw_liters)
    executor = IrrigationExecutor(
        actuators=plant,
        meter=HomeAssistantMeter(hass, plant.meter_entity_id),
        flow=plant,
        clock=plant.clock,
    )

    result = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=plant.main_valve,
            amount_liters=2,
            hard_time_limit_seconds=60,
            monitor_interval_seconds=1,
        )
    )

    assert result.target_reached is target_reached
    assert result.delivered_liters == expected_liters
    assert (error_text is None) is (result.safety_violation is None)
    if error_text is not None:
        assert error_text in (result.safety_violation or "")
    assert plant.open_valves == set()


@pytest.mark.parametrize(
    ("strategy", "expected_quality", "target_reached"),
    [("abort", "measured", False), ("estimated_time_fallback", "estimated", True)],
)
async def test_volume_meter_loss_aborts_or_uses_explicit_estimated_fallback(
    hass: HomeAssistant,
    strategy: str,
    expected_quality: str,
    target_reached: bool,
) -> None:
    """Apply the configured meter-loss strategy and retain partial delivery."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 60})
    plant.meter_script = [100.0, 104.0, RuntimeError("offline"), RuntimeError("offline")]

    result = await _executor(plant).execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=plant.main_valve,
            amount_liters=10,
            hard_time_limit_seconds=20,
            monitor_interval_seconds=1,
            meter_failure_strategy=strategy,
            estimated_flow_l_min=60,
        )
    )

    assert result.measurement_quality == expected_quality
    assert result.target_reached is target_reached
    assert result.delivered_liters >= 4
    assert plant.open_valves == set()


async def test_volume_deadline_ignores_backward_wall_clock_jump(hass: HomeAssistant) -> None:
    """Use monotonic time for the hard deadline despite a discontinuous wall clock."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 1})
    original_advance = plant.clock.on_advance

    def advance_with_wall_jump(seconds: float) -> None:
        assert original_advance is not None
        original_advance(seconds)
        plant.clock.jump_wall(timedelta(hours=-12))

    plant.clock.on_advance = advance_with_wall_jump
    result = await _executor(plant).execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=plant.main_valve,
            amount_liters=10,
            hard_time_limit_seconds=3,
            monitor_interval_seconds=1,
        )
    )

    assert result.duration_seconds == 3
    assert not result.target_reached
    assert result.safety_violation == "Hard time limit reached before volume target"
    assert plant.open_valves == set()


async def test_idle_leak_and_weather_idempotency_survive_restart(hass: HomeAssistant) -> None:
    """Persist an idle leak lock and apply one finalized weather period only once."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(
        with_meter=False,
        installation_data={"leak_duration_seconds": 0.01, "leak_flow_threshold": 0.5},
        zone_data=({"automation_enabled": False},),
    )
    manager = entry.runtime_data.manager
    first = await manager.async_finalize_daily_weather(
        period_id="2026-07-20",
        reference_evapotranspiration_mm=5,
        rain_mm=2,
    )
    second = await manager.async_finalize_daily_weather(
        period_id="2026-07-20",
        reference_evapotranspiration_mm=5,
        rain_mm=2,
    )
    plant.set_flow(60)
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()

    before_restart = await IrrigationStore(hass, entry.entry_id).async_load()
    assert first["applied"] is True
    assert second["applied"] is False
    assert before_restart.installation_safety_lock is not None
    assert before_restart.unassigned_total_liters > 0

    await plant.restart()
    after_restart = await IrrigationStore(hass, entry.entry_id).async_load()
    assert after_restart.installation_safety_lock == before_restart.installation_safety_lock
    assert after_restart.finalized_weather_periods == before_restart.finalized_weather_periods
    assert plant.open_valves == set()


async def test_duplicate_planning_events_create_one_stable_request(hass: HomeAssistant) -> None:
    """Make repeated scheduler events idempotent for one zone/window opportunity."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(
        zone_data=(
            {
                "automation_enabled": True,
                "watering_mode": "demand",
                "area_m2": 10,
                "application_efficiency": 0.5,
                "maximum_deficit_mm": 50,
                "minimum_interval_days": 1,
                "maximum_interval_days": 7,
                "minimum_trigger_liters": 1,
                "minimum_effective_liters": 1,
                "maximum_target_liters": 100,
                "automatic_max_duration": 3600,
                "watering_windows": ["03:00-05:00"],
            },
        )
    )
    manager = entry.runtime_data.manager
    planner = manager._automatic_planner_task
    dispatcher = manager._dispatcher_task
    for task in (planner, dispatcher):
        if task is not None:
            task.cancel()
    await asyncio.gather(
        *(task for task in (planner, dispatcher) if task is not None),
        return_exceptions=True,
    )
    manager._automatic_planner_task = None
    manager._dispatcher_task = None
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"qualification-zone-1": 10},
        zone_last_effective_irrigation={
            "qualification-zone-1": (now - timedelta(days=2)).isoformat()
        },
    )

    first = await manager.async_plan_automatic(now=now)
    second = await manager.async_plan_automatic(now=now)

    automatic = [
        request
        for request in manager._stored_state.manual_requests
        if request.source == "automatic"
    ]
    assert len(automatic) == 1
    assert first["created_request_ids"] == [automatic[0].request_id]
    assert second["created_request_ids"] == []


async def test_soaking_state_is_interrupted_before_remainder_is_replanned(
    hass: HomeAssistant,
) -> None:
    """Never blindly continue a persisted open execution or hydraulic pause."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="soaking-request",
        sequence=1,
        zone_id="qualification-zone-1",
        zone_subentry_id="qualification-zone-1",
        zone_name="Zone 1",
        zone_valve="switch.zone_lawn",
        main_valve=plant.main_valve,
        target_type="duration",
        target_value=0.001,
        remaining_value=0.001,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        status="soaking",
        soak_until=(now + timedelta(hours=1)).isoformat(),
        execution_id="soaking-execution",
    )
    execution = IrrigationExecutionState(
        execution_id="soaking-execution",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type=request.target_type,
        target_value=request.target_value,
        remaining_value=request.remaining_value,
        status="soaking",
        created_at=request.created_at,
    )
    entry = await plant.setup_entry(zone_data=({},))
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(manual_requests=(request,), irrigation_executions=(execution,))
    )
    plant.operations.clear()

    await plant.restart()

    state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert state.irrigation_executions[0].status == "interrupted"
    assert state.irrigation_executions[0].result == "restart"
    if state.manual_requests[0].status != "pending":
        assert state.manual_requests[0].execution_id != "soaking-execution"
    assert state.active_execution is None
    assert plant.open_valves == set()


async def test_storage_migration_is_additive_and_corruption_fails_closed(
    hass: HomeAssistant,
) -> None:
    """Preserve legacy totals but refuse malformed safety-critical state."""
    await Store[dict[str, object]](
        hass,
        1,
        "irrigation_manager.qualification-legacy",
        atomic_writes=True,
        minor_version=1,
    ).async_save(
        {
            "installation_total_liters": 12.0,
            "zone_totals_liters": {"zone-1": 12.0},
            "zone_measurement_quality": {"zone-1": "measured"},
            "unassigned_total_liters": 0.0,
            "emergency_stop": False,
        }
    )
    migrated = await IrrigationStore(hass, "qualification-legacy").async_load()
    assert migrated.installation_total_liters == 12
    assert migrated.manual_requests == ()
    assert migrated.active_execution is None

    await Store[dict[str, object]](
        hass,
        1,
        "irrigation_manager.qualification-corrupt",
        atomic_writes=True,
        minor_version=12,
    ).async_save({"emergency_stop": "false"})
    with pytest.raises(ValueError, match="emergency stop"):
        await IrrigationStore(hass, "qualification-corrupt").async_load()


async def test_config_reload_waits_for_idle_and_unload_cleans_runtime_tasks(
    hass: HomeAssistant,
) -> None:
    """Keep an immutable active snapshot and remove listeners/tasks on unload."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    entry = await plant.setup_entry(zone_data=({"max_dose_duration": 60},))
    manager = entry.runtime_data.manager
    manager._executor = _executor(plant)
    response = await manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=60,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await plant.clock.sleeping.wait()
    old_manager = manager
    await manager.async_request_config_reload()
    await asyncio.sleep(0)
    assert entry.runtime_data.manager is old_manager

    await manager.async_cancel_request(str(response["request_id"]))
    async with asyncio.timeout(2):
        while entry.runtime_data.manager is old_manager:  # noqa: ASYNC110 - reload has no event seam
            await asyncio.sleep(0.001)
    reloaded_manager = entry.runtime_data.manager
    assert reloaded_manager is not old_manager

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert reloaded_manager._dispatcher_task is None
    assert reloaded_manager._automatic_planner_task is None
    assert reloaded_manager._unsubscribe_flow is None
    assert not reloaded_manager._flow_event_tasks
    assert reloaded_manager._pending_reload_task is None
    assert hass.states.get("switch.zone_lawn").state == STATE_OFF


async def test_finalized_weather_rejects_nan_without_mutating_balance(
    hass: HomeAssistant,
) -> None:
    """Reject unavailable-quality numeric weather input rather than persisting NaN."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(zone_data=({},))
    manager = entry.runtime_data.manager
    before = manager._stored_state

    with pytest.raises(HomeAssistantError, match="finite and non-negative"):
        await manager.async_finalize_daily_weather(
            period_id="bad-weather",
            reference_evapotranspiration_mm=float("nan"),
            rain_mm=0,
        )

    assert manager._stored_state == before


async def test_idle_unexpected_valve_open_closes_and_locks_without_flow_sensor(
    hass: HomeAssistant,
) -> None:
    """Supervise actuators continuously even when no flow safety is available."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(with_flow=False, with_meter=False)

    plant.force_feedback("switch.zone_lawn", open_=True)
    async with asyncio.timeout(2):
        while (  # noqa: ASYNC110 - the state transition is the production test seam
            entry.runtime_data.manager._stored_state.installation_safety_lock is None
        ):
            await asyncio.sleep(0.001)

    assert plant.open_valves == set()
    assert "opened unexpectedly" in (
        entry.runtime_data.manager._stored_state.installation_safety_lock or ""
    )


async def test_active_unexpected_main_closure_aborts_and_locks_without_flow_sensor(
    hass: HomeAssistant,
) -> None:
    """Abort an active operation when unsolicited feedback closes the main valve."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    entry = await plant.setup_entry(with_flow=False, with_meter=False)
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=None,
        clock=plant.clock,
    )
    response = await manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=60,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await plant.clock.sleeping.wait()

    plant.force_feedback(plant.main_valve or "", open_=False)
    async with asyncio.timeout(2):
        while manager._stored_state.installation_safety_lock is None:  # noqa: ASYNC110
            await asyncio.sleep(0.001)
    await manager._terminal_events[str(response["request_id"])].wait()

    request = manager._request(str(response["request_id"]))
    assert request is not None
    assert request.status == "cancelled"
    assert "closed unexpectedly" in (manager._stored_state.installation_safety_lock or "")
    assert plant.open_valves == set()


async def test_commanded_transitions_do_not_trigger_actuator_supervision(
    hass: HomeAssistant,
) -> None:
    """Do not classify the integration's own immediate feedback as unsolicited."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(with_flow=False, with_meter=False)

    await entry.runtime_data.manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=0.01,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )

    assert entry.runtime_data.manager._stored_state.installation_safety_lock is None
    assert plant.open_valves == set()


async def test_weather_interlocks_fail_safe_and_allow_manual_rain_override(
    hass: HomeAssistant,
) -> None:
    """Block frost globally, rain automatically, and expose invalid sources as unsafe."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    hass.states.async_set("sensor.frost", "-1", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.rain", "0")
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "frost_entity": "sensor.frost",
            "frost_threshold": 2,
            "rain_stop_entity": "sensor.rain",
            "rain_stop_threshold": 0.1,
            "weather_max_age_seconds": 300,
        },
        zone_data=({"automation_enabled": True, "watering_windows": ["00:00-23:59"]},),
    )
    manager = entry.runtime_data.manager

    with pytest.raises(HomeAssistantError, match="Frost safety"):
        await manager.async_start_manual(
            zone_subentry_id="qualification-zone-1",
            duration_seconds=1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )

    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.rain", "1")
    await hass.async_block_till_done()
    report = await manager.async_plan_automatic(dry_run=True)
    assert report["zones"][0]["reason"] == "safety_blocked"

    response = await manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=0.01,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    assert response["request_id"]

    hass.states.async_set("sensor.frost", "unavailable", {"unit_of_measurement": "°C"})
    await hass.async_block_till_done()
    assert manager._weather_safety().frost_blocked
    assert "frost_source_invalid" in manager._weather_safety().status


async def test_runtime_snapshots_use_minimum_limits_and_lifetime_includes_soaking(
    hass: HomeAssistant,
) -> None:
    """Persist minimum safety ceilings and expire the operation during its soak."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "installation_max_delivery_runtime": 0.03,
            "installation_max_operation_lifetime": 0.03,
        },
        zone_data=(
            {
                "max_delivery_runtime": 1,
                "max_operation_lifetime": 1,
                "max_dose_duration": 0.01,
                "soak_duration": 0.1,
            },
        ),
    )
    manager = entry.runtime_data.manager

    response = await manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=0.02,
        amount_liters=None,
        hard_time_limit_seconds=None,
        expiry_seconds=60,
    )
    request = manager._request(str(response["request_id"]))
    assert request is not None
    assert request.delivery_runtime_limit_seconds == pytest.approx(0.03)
    assert request.operation_deadline_at is not None
    assert datetime.fromisoformat(request.operation_deadline_at) < datetime.fromisoformat(
        request.expires_at
    )
    assert request.status == "expired"
    execution = manager._execution(request.execution_id)
    assert execution is not None
    assert execution.delivery_runtime_limit_seconds == pytest.approx(0.03)
    assert execution.operation_deadline_at == request.operation_deadline_at

    deadline = request.operation_deadline_at
    delivery_limit = request.delivery_runtime_limit_seconds
    await plant.restart()
    restarted = await IrrigationStore(hass, entry.entry_id).async_load()
    persisted = next(
        item for item in restarted.manual_requests if item.request_id == request.request_id
    )
    assert persisted.operation_deadline_at == deadline
    assert persisted.delivery_runtime_limit_seconds == delivery_limit


@pytest.mark.parametrize(
    ("kind", "unsafe_entity", "unsafe_value"),
    [
        ("maintenance", "sensor.frost", "-5"),
        ("calibration", "sensor.rain", STATE_UNAVAILABLE),
    ],
)
async def test_weather_unsafe_stops_supervised_tests_without_leaking_violation(
    hass: HomeAssistant,
    kind: str,
    unsafe_entity: str,
    unsafe_value: str,
) -> None:
    """Stop maintenance and calibration, then keep the violation out of the next run."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.rain", "0")
    entry = await plant.setup_entry(
        installation_data={
            "frost_entity": "sensor.frost",
            "rain_stop_entity": "sensor.rain",
            "weather_max_age_seconds": 300,
            "maintenance_confirmation_interval": 10,
        }
    )
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=plant,
        clock=plant.clock,
    )
    await manager.async_start_maintenance_test(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=5,
        kind=kind,
    )
    await plant.clock.sleeping.wait()

    attributes = {"unit_of_measurement": "°C"} if unsafe_entity == "sensor.frost" else {}
    hass.states.async_set(unsafe_entity, unsafe_value, attributes)
    await manager._async_apply_weather_interlocks()
    async with asyncio.timeout(2):
        while manager._stored_state.maintenance_test is not None:  # noqa: ASYNC110
            await asyncio.sleep(0.001)

    assert manager._active_external_violation is None
    if kind == "calibration":
        assert manager._stored_state.calibration_proposal is None

    plant.clock.auto_advance = True
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.rain", "0")
    await hass.async_block_till_done()
    await manager.async_start_maintenance_test(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=0.01,
        kind="maintenance",
    )
    task = manager._maintenance_task
    assert task is not None
    result = await task
    assert result.safety_violation is None


@pytest.mark.parametrize(
    ("entity_id", "state", "lock_scope"),
    [
        ("switch.irrigation_main", STATE_UNKNOWN, "installation"),
        ("switch.irrigation_main", STATE_UNAVAILABLE, "installation"),
        ("switch.zone_lawn", STATE_UNKNOWN, "zone"),
        ("switch.zone_lawn", STATE_UNAVAILABLE, "zone"),
    ],
)
async def test_unavailable_active_feedback_fails_after_configured_grace(
    hass: HomeAssistant,
    entity_id: str,
    state: str,
    lock_scope: str,
) -> None:
    """Allow only the command grace before unknown active feedback fails closed."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={"actuator_transition_grace_seconds": 0.02},
    )
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=None,
        clock=plant.clock,
    )
    await manager.async_start_manual(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=60,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await plant.clock.sleeping.wait()

    hass.states.async_set(entity_id, state)
    await asyncio.sleep(0.005)
    assert manager._stored_state.installation_safety_lock is None
    assert manager._stored_state.zone_safety_locks == {}
    await asyncio.sleep(0.03)

    if lock_scope == "installation":
        assert "feedback unavailable" in (manager._stored_state.installation_safety_lock or "")
    else:
        assert (
            "feedback unavailable"
            in manager._stored_state.zone_safety_locks["qualification-zone-1"]
        )
    assert plant.open_valves == set()


async def test_unavailable_feedback_stops_supervised_test_after_grace(
    hass: HomeAssistant,
) -> None:
    """Apply the same feedback watchdog to maintenance and calibration execution."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "actuator_transition_grace_seconds": 0.02,
            "maintenance_confirmation_interval": 10,
        },
    )
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=None,
        clock=plant.clock,
    )
    await manager.async_start_maintenance_test(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=5,
        bypass_checks=("flow",),
    )
    await plant.clock.sleeping.wait()

    hass.states.async_set("switch.irrigation_main", STATE_UNAVAILABLE)
    await asyncio.sleep(0.03)

    assert manager._stored_state.maintenance_test is None
    assert manager._stored_state.installation_safety_lock is not None
    assert plant.open_valves == set()


async def test_startup_listener_gap_is_closed_by_authoritative_final_check(
    hass: HomeAssistant,
) -> None:
    """Catch a valve opening injected exactly after listener registration."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    original = IrrigationManager._async_verify_supervised_valves_after_startup

    async def inject_open(manager: IrrigationManager) -> None:
        plant.force_feedback("switch.zone_lawn", open_=True)
        await original(manager)

    with patch.object(
        IrrigationManager,
        "_async_verify_supervised_valves_after_startup",
        inject_open,
    ):
        entry = await plant.setup_entry(with_flow=False, with_meter=False)

    assert "opened unexpectedly" in (
        entry.runtime_data.manager._stored_state.installation_safety_lock or ""
    )
    assert plant.open_valves == set()


async def test_startup_unavailable_feedback_does_not_create_false_lock(
    hass: HomeAssistant,
) -> None:
    """Do not lock merely because startup feedback is temporarily unavailable."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    original = IrrigationManager._async_verify_supervised_valves_after_startup

    async def inject_unavailable(manager: IrrigationManager) -> None:
        hass.states.async_set("switch.zone_lawn", STATE_UNAVAILABLE)
        await original(manager)

    with patch.object(
        IrrigationManager,
        "_async_verify_supervised_valves_after_startup",
        inject_unavailable,
    ):
        entry = await plant.setup_entry(with_flow=False, with_meter=False)

    assert entry.runtime_data.manager._stored_state.installation_safety_lock is None
    assert entry.runtime_data.manager._stored_state.zone_safety_locks == {}


async def test_weather_freshness_watchdog_stops_test_without_state_event(
    hass: HomeAssistant,
) -> None:
    """Stop an active test when its unchanged weather sample merely becomes stale."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "frost_entity": "sensor.frost",
            "weather_max_age_seconds": 0.03,
            "maintenance_confirmation_interval": 10,
        },
    )
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=None,
        clock=plant.clock,
    )
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    await manager.async_start_maintenance_test(
        zone_subentry_id="qualification-zone-1",
        duration_seconds=5,
        bypass_checks=("flow",),
    )
    await plant.clock.sleeping.wait()

    async with asyncio.timeout(2):
        while manager._stored_state.maintenance_test is not None:  # noqa: ASYNC110
            await asyncio.sleep(0.001)

    assert manager._active_external_violation is None
    assert plant.open_valves == set()


async def test_weather_freshness_watchdog_stops_automatic_watering_without_event(
    hass: HomeAssistant,
) -> None:
    """Apply timer-driven freshness failure to active automatic watering too."""
    plant = FakeHaIrrigationPlant(
        hass,
        zone_flows_l_min={"switch.zone_lawn": 10},
        auto_advance=False,
    )
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "frost_entity": "sensor.frost",
            "weather_max_age_seconds": 0.05,
        },
        zone_data=(
            {
                "automation_enabled": True,
                "watering_mode": "demand",
                "area_m2": 10,
                "application_efficiency": 0.5,
                "maximum_deficit_mm": 50,
                "minimum_interval_days": 0,
                "maximum_interval_days": 7,
                "minimum_trigger_liters": 0.01,
                "minimum_effective_liters": 0.01,
                "maximum_target_liters": 100,
                "automatic_max_duration": 60,
                "watering_windows": ["00:00-23:59"],
            },
        ),
    )
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=None,
        clock=plant.clock,
    )
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"qualification-zone-1": 1},
        zone_last_effective_irrigation={
            "qualification-zone-1": (datetime.now(UTC) - timedelta(days=1)).isoformat()
        },
    )
    hass.states.async_set("sensor.frost", "10", {"unit_of_measurement": "°C"})
    report = await manager.async_plan_automatic(now=datetime.now(UTC))
    assert report["created_request_ids"]
    request_id = str(report["created_request_ids"][0])
    await plant.clock.sleeping.wait()

    async with asyncio.timeout(2):
        while manager._request(request_id).status not in {  # noqa: ASYNC110
            "cancelled",
            "expired",
        }:
            await asyncio.sleep(0.001)

    request = manager._request(request_id)
    assert request is not None
    assert request.status == "cancelled"
    assert plant.open_valves == set()


async def test_minor_14_duration_runtime_limits_are_derived_before_execution(
    hass: HomeAssistant,
) -> None:
    """Migrate non-null conservative limits, refine from config, and execute safely."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min={"switch.zone_lawn": 10})
    entry = await plant.setup_entry(
        with_flow=False,
        with_meter=False,
        installation_data={
            "installation_max_delivery_runtime": 0.05,
            "installation_max_operation_lifetime": 0.06,
        },
        zone_data=({"max_delivery_runtime": 0.03, "max_operation_lifetime": 0.04},),
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="legacy-duration",
        sequence=1,
        zone_id="qualification-zone-1",
        zone_subentry_id="qualification-zone-1",
        zone_name="Zone 1",
        zone_valve="switch.zone_lawn",
        main_valve=plant.main_valve,
        target_type="duration",
        target_value=0.01,
        remaining_value=0.01,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=1)).isoformat(),
        execution_id="legacy-execution",
    ).as_dict()
    execution = IrrigationExecutionState(
        execution_id="legacy-execution",
        request_id="legacy-duration",
        zone_id="qualification-zone-1",
        target_type="duration",
        target_value=0.01,
        remaining_value=0.01,
        status="waiting",
        created_at=now.isoformat(),
    ).as_dict()
    for record in (request, execution):
        record.pop("delivery_runtime_limit_seconds", None)
        record.pop("operation_deadline_at", None)
        record.pop("runtime_limits_need_config_derivation", None)
    await Store[dict[str, object]](
        hass,
        1,
        f"irrigation_manager.{entry.entry_id}",
        atomic_writes=True,
        minor_version=14,
    ).async_save(
        {
            "manual_requests": [request],
            "irrigation_executions": [execution],
            "next_request_sequence": 2,
        }
    )

    raw_migrated = await IrrigationStore(hass, entry.entry_id).async_load()
    assert raw_migrated.manual_requests[0].delivery_runtime_limit_seconds is not None
    assert raw_migrated.manual_requests[0].operation_deadline_at is not None
    assert raw_migrated.irrigation_executions[0].delivery_runtime_limit_seconds is not None
    assert raw_migrated.irrigation_executions[0].operation_deadline_at is not None

    assert await hass.config_entries.async_setup(entry.entry_id)
    async with asyncio.timeout(2):
        while (  # noqa: ASYNC110
            entry.runtime_data.manager._request("legacy-duration").status != "completed"
        ):
            await asyncio.sleep(0.001)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    migrated_request = next(
        item for item in stored.manual_requests if item.request_id == "legacy-duration"
    )
    migrated_execution = next(
        item for item in stored.irrigation_executions if item.execution_id == "legacy-execution"
    )
    assert migrated_request.delivery_runtime_limit_seconds == pytest.approx(0.03)
    assert migrated_execution.delivery_runtime_limit_seconds == pytest.approx(0.03)
    assert migrated_request.runtime_limits_need_config_derivation is False
    assert migrated_execution.runtime_limits_need_config_derivation is False
