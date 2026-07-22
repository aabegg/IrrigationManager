"""Phase-5 production-path qualification across six reference zones."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant

from custom_components.irrigation_manager.executor import ExecutionRequest, IrrigationExecutor
from custom_components.irrigation_manager.scheduler import active_and_next_window
from custom_components.irrigation_manager.storage import IrrigationStore
from custom_components.irrigation_manager.weather import RainForecast
from tests.irrigation_plant import FakeHaIrrigationPlant

REFERENCE_FLOWS = {
    "switch.zone_lawn": 12.0,
    "switch.zone_beds": 8.0,
    "switch.zone_hedge": 6.0,
    "switch.zone_pots": 4.0,
    "switch.zone_front": 10.0,
    "switch.zone_orchard": 14.0,
}


async def _stop_background_tasks(manager: object) -> None:
    """Stop autonomous loops while a test drives production methods deterministically."""
    tasks = [
        task
        for name in ("_automatic_planner_task", "_dispatcher_task")
        if (task := getattr(manager, name)) is not None
    ]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for name in ("_automatic_planner_task", "_dispatcher_task"):
        setattr(manager, name, None)


def _zone_data(*, automatic: bool) -> tuple[dict[str, object], ...]:
    """Return six distinct production zone configurations."""
    return tuple(
        {
            "automation_enabled": automatic,
            "agronomic_values_confirmed": True,
            "watering_mode": "demand",
            "area_m2": area,
            "application_efficiency": efficiency,
            "crop_factor": crop,
            "rain_factor": rain,
            "maximum_deficit_mm": maximum,
            "minimum_interval_days": 0,
            "maximum_interval_days": 7,
            "minimum_trigger_liters": 1,
            "minimum_effective_liters": 0.1,
            "maximum_target_liters": 100,
            "automatic_max_duration": 3600,
            "watering_windows": ["00:00-23:59"],
            "max_dose_duration": 3,
            "soak_duration": 0.01,
        }
        for area, efficiency, crop, rain, maximum in (
            (45, 0.78, 1.00, 1.00, 42),
            (24, 0.82, 0.85, 0.95, 38),
            (18, 0.88, 0.72, 0.80, 35),
            (6, 0.70, 1.15, 0.35, 22),
            (30, 0.80, 0.90, 0.90, 40),
            (55, 0.75, 0.68, 1.00, 48),
        )
    )


async def test_six_zone_multiweek_weather_balance_uses_manager_and_is_idempotent(
    hass: HomeAssistant,
) -> None:
    """Finalize 28 dry/rain periods through manager storage, including a restart."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min=REFERENCE_FLOWS)
    entry = await plant.setup_entry(zone_data=_zone_data(automatic=False))
    manager = entry.runtime_data.manager
    await _stop_background_tasks(manager)
    dry_week_total: float | None = None
    rainy_total: float | None = None

    for day_index in range(28):
        period = date(2026, 3, 15) + timedelta(days=day_index)
        rain_mm = 18.0 if day_index in {7, 8, 21} else 0.0
        et0_mm = 5.5 if day_index < 7 or 14 <= day_index < 21 else 3.2
        first = await manager.async_finalize_daily_weather(
            period_id=period.isoformat(),
            reference_evapotranspiration_mm=et0_mm,
            rain_mm=rain_mm,
        )
        state_after_first = await IrrigationStore(hass, entry.entry_id).async_load()
        second = await manager.async_finalize_daily_weather(
            period_id=period.isoformat(),
            reference_evapotranspiration_mm=et0_mm,
            rain_mm=rain_mm,
        )
        state_after_second = await IrrigationStore(hass, entry.entry_id).async_load()

        assert first["applied"] is True
        assert second["applied"] is False
        assert state_after_second == state_after_first
        if day_index == 6:
            dry_week_total = sum(state_after_first.zone_deficit_mm.values())
        if day_index == 8:
            rainy_total = sum(state_after_first.zone_deficit_mm.values())
        if day_index == 13:
            await plant.restart()
            manager = entry.runtime_data.manager
            await _stop_background_tasks(manager)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert len(stored.finalized_weather_periods) == 28
    assert set(stored.zone_deficit_mm) == {f"qualification-zone-{index}" for index in range(1, 7)}
    assert dry_week_total is not None
    assert rainy_total is not None
    assert rainy_total < dry_week_total
    assert all(value >= 0 for value in stored.zone_deficit_mm.values())


async def test_forecast_budget_and_duplicate_planning_survive_restart(
    hass: HomeAssistant,
) -> None:
    """Invoke production forecast deferral, budget claims, persistence, and replanning."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min=REFERENCE_FLOWS)
    entry = await plant.setup_entry(
        installation_data={
            "installation_daily_budget_liters": 30,
            "installation_weekly_budget_liters": 100,
        },
        zone_data=_zone_data(automatic=True),
    )
    manager = entry.runtime_data.manager
    await _stop_background_tasks(manager)
    now = datetime(2026, 7, 21, 12, tzinfo=UTC)
    zone_ids = {f"qualification-zone-{index}" for index in range(1, 7)}
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm=dict.fromkeys(zone_ids, 10.0),
        zone_last_effective_irrigation=dict.fromkeys(
            zone_ids, (now - timedelta(days=2)).isoformat()
        ),
    )
    await manager._store.async_save(manager._stored_state)
    manager._rain_forecast = RainForecast(
        amount_mm=30,
        probability_percent=90,
        valid_at=now + timedelta(hours=4),
        issued_at=now,
        source="qualification",
        quality="forecast",
    )

    deferred = await manager.async_plan_automatic(now=now)
    duplicate_deferred = await manager.async_plan_automatic(now=now)
    assert deferred["created_request_ids"] == []
    assert duplicate_deferred["created_request_ids"] == []
    assert {zone["reason"] for zone in deferred["zones"]} == {"forecast_rain_deferred"}
    deadlines = dict(manager._stored_state.forecast_deferral_deadlines)

    await plant.restart()
    manager = entry.runtime_data.manager
    await _stop_background_tasks(manager)
    persisted = await manager.async_plan_automatic(now=now + timedelta(minutes=5))
    assert {zone["reason"] for zone in persisted["zones"]} == {"forecast_rain_deferred"}
    assert manager._stored_state.forecast_deferral_deadlines == deadlines

    after_deadline = now + timedelta(hours=25)
    manager._rain_forecast = RainForecast(
        amount_mm=30,
        probability_percent=90,
        valid_at=after_deadline + timedelta(hours=2),
        issued_at=after_deadline,
        source="qualification",
        quality="forecast",
    )
    planned = await manager.async_plan_automatic(now=after_deadline)
    duplicate_planned = await manager.async_plan_automatic(now=after_deadline)
    requests = [manager._request(str(request_id)) for request_id in planned["created_request_ids"]]
    assert planned["created_request_ids"]
    assert duplicate_planned["created_request_ids"] == []
    assert sum(request.target_value for request in requests if request is not None) <= 30

    request_ids = {request.request_id for request in requests if request is not None}
    await plant.restart()
    manager = entry.runtime_data.manager
    await _stop_background_tasks(manager)
    after_restart = await manager.async_plan_automatic(now=after_deadline)
    persisted_request_ids = {
        request.request_id for request in manager._stored_state.manual_requests
    }
    assert request_ids <= persisted_request_ids
    assert set(after_restart["created_request_ids"]).isdisjoint(request_ids)
    assert len(persisted_request_ids) == len(manager._stored_state.manual_requests)


async def test_meter_deltas_conserve_persisted_zone_and_unassigned_accounting(
    hass: HomeAssistant,
) -> None:
    """Reconcile independently observed physical deltas with durable manager accounting."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min=REFERENCE_FLOWS)
    entry = await plant.setup_entry(zone_data=_zone_data(automatic=False))
    manager = entry.runtime_data.manager
    manager._executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=plant,
        clock=plant.clock,
    )
    physical_start = plant.meter_liters
    observed_zone_deltas: dict[str, float] = {}

    for index, subentry in enumerate(entry.get_subentries_of_type("zone"), start=1):
        before = plant.meter_liters
        await manager.async_start_manual(
            zone_subentry_id=subentry.subentry_id,
            duration_seconds=6,
            amount_liters=None,
            hard_time_limit_seconds=None,
        )
        observed_zone_deltas[f"qualification-zone-{index}"] = plant.meter_liters - before

    before_unassigned = plant.meter_liters
    await manager.async_start_maintenance_test(
        zone_subentry_id=entry.get_subentries_of_type("zone")[0].subentry_id,
        duration_seconds=6,
        water_attribution="unassigned",
    )
    maintenance_task = manager._maintenance_task
    assert maintenance_task is not None
    await maintenance_task
    observed_unassigned_delta = plant.meter_liters - before_unassigned
    observed_total_delta = plant.meter_liters - physical_start

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_total_liters == pytest.approx(observed_total_delta)
    assert stored.zone_totals_liters == pytest.approx(observed_zone_deltas)
    assert stored.unassigned_total_liters == pytest.approx(observed_unassigned_delta)
    assert stored.installation_total_liters == pytest.approx(
        sum(stored.zone_totals_liters.values()) + stored.unassigned_total_liters
    )

    await plant.restart()
    restarted = await IrrigationStore(hass, entry.entry_id).async_load()
    assert restarted.installation_total_liters == stored.installation_total_liters
    assert restarted.zone_totals_liters == stored.zone_totals_liters
    assert restarted.unassigned_total_liters == stored.unassigned_total_liters


def test_cross_midnight_windows_span_spring_and_fall_dst() -> None:
    """Resolve cross-midnight Europe/Berlin windows across both clock transitions."""
    berlin = ZoneInfo("Europe/Berlin")
    spring, _ = active_and_next_window(
        now=datetime(2026, 3, 29, 1, tzinfo=berlin), values=["22:00-04:00"]
    )
    fall, _ = active_and_next_window(
        now=datetime(2026, 10, 25, 1, tzinfo=berlin), values=["22:00-04:00"]
    )

    assert spring is not None
    assert spring.start.date() == date(2026, 3, 28)
    assert spring.end - spring.start == timedelta(hours=5)
    assert fall is not None
    assert fall.start.date() == date(2026, 10, 24)
    assert fall.end - fall.start == timedelta(hours=7)


async def test_six_zone_fault_matrix_closes_or_hydraulically_isolates_flow(
    hass: HomeAssistant,
) -> None:
    """Inject sensor, leak, and valve faults without overlap or unbounded flow."""
    plant = FakeHaIrrigationPlant(hass, zone_flows_l_min=REFERENCE_FLOWS)
    executor = IrrigationExecutor(
        actuators=plant,
        meter=plant,
        flow=plant,
        clock=plant.clock,
    )
    plant.meter_script = [0.0, RuntimeError("meter offline"), RuntimeError("meter offline")]
    sensor_fault = await executor.execute(
        ExecutionRequest(
            zone_id="lawn",
            zone_valve="switch.zone_lawn",
            main_valve=plant.main_valve,
            amount_liters=10,
            hard_time_limit_seconds=5,
            monitor_interval_seconds=1,
            managed_zone_valves=plant.zone_valves,
        )
    )
    assert not sensor_fault.target_reached
    assert plant.open_valves == set()

    plant.fail_close.add("switch.zone_beds")
    valve_fault = await executor.execute(
        ExecutionRequest(
            zone_id="beds",
            zone_valve="switch.zone_beds",
            main_valve=plant.main_valve,
            duration_seconds=2,
            monitor_interval_seconds=1,
            managed_zone_valves=plant.zone_valves,
        )
    )
    assert valve_fault.safety_violation is not None
    assert plant.main_valve not in plant.open_valves
    assert await plant.read_l_min() == 0
    plant.fail_close.clear()
    await plant.close("switch.zone_beds")

    entry = await plant.setup_entry(
        with_meter=False,
        installation_data={"leak_duration_seconds": 0.01, "leak_flow_threshold": 0.5},
        zone_data=({"automation_enabled": False},) * len(REFERENCE_FLOWS),
        unique_id="phase5-fault-installation",
    )
    plant.set_flow(30)
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()
    assert entry.runtime_data.manager._stored_state.installation_safety_lock is not None
    assert plant.maximum_simultaneous_zones <= 1
    assert plant.open_valves == set()
