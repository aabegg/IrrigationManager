"""Automatic scheduling and persistent water-balance integration tests."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.executor import ExecutionResult
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
)
from custom_components.irrigation_manager.storage import IrrigationStore
from custom_components.irrigation_manager.weather import DailyWeather, RainForecast, WeatherValue


async def _setup_automatic_zone(
    hass: HomeAssistant,
) -> tuple[MockConfigEntry, ConfigSubentry]:
    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden irrigation",
        data={"name": "Garden irrigation"},
        unique_id="installation-automatic",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 60,
                "min_flow": 10,
                "max_flow": 10,
                "automation_enabled": True,
                "watering_mode": "demand",
                "area_m2": 10,
                "application_efficiency": 0.5,
                "crop_factor": 1,
                "rain_factor": 1,
                "maximum_deficit_mm": 50,
                "minimum_interval_days": 1,
                "maximum_interval_days": 7,
                "minimum_trigger_liters": 1,
                "mandatory_amount_liters": 5,
                "minimum_effective_liters": 2,
                "maximum_target_liters": 100,
                "automatic_max_duration": 3600,
                "zone_priority": 1,
                "watering_windows": ["03:00-05:00", "22:00-02:00"],
            }
        ),
        subentry_id="subentry-lawn",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-lawn",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    await _stop_background_planning(entry)
    return entry, subentry


async def _stop_background_planning(entry: MockConfigEntry) -> None:
    """Stop runtime loops so tests can drive deterministic planning instants."""
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


def _make_zone_due(entry: MockConfigEntry, now: datetime, *, deficit_mm: float = 10) -> None:
    manager = entry.runtime_data.manager
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": deficit_mm},
        zone_last_effective_irrigation={"zone-lawn": (now - timedelta(days=2)).isoformat()},
    )


async def test_automatic_planning_is_idempotent_across_repeated_persisted_plans(
    hass: HomeAssistant,
) -> None:
    """Create one durable request for one zone/window opportunity only once."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now)

    first = await entry.runtime_data.manager.async_plan_automatic(now=now)
    second = await entry.runtime_data.manager.async_plan_automatic(now=now)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    automatic = [request for request in stored.manual_requests if request.source == "automatic"]
    assert len(automatic) == 1
    assert automatic[0].request_id == "automatic:zone-lawn:2026-07-21T03:00:00+00:00"
    assert first["created_request_ids"] == [automatic[0].request_id]
    assert second["created_request_ids"] == []


async def test_restart_does_not_duplicate_a_persisted_window_opportunity(
    hass: HomeAssistant,
) -> None:
    """Retain the deterministic opportunity identity through a full entry reload."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now)
    await entry.runtime_data.manager.async_plan_automatic(now=now)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _stop_background_planning(entry)
    await entry.runtime_data.manager.async_plan_automatic(now=now)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    opportunity_id = "automatic:zone-lawn:2026-07-21T03:00:00+00:00"
    assert sum(request.request_id == opportunity_id for request in stored.manual_requests) == 1


async def test_dry_run_reports_request_without_mutating_persistent_state(
    hass: HomeAssistant,
) -> None:
    """Use the production planning path without creating or expiring requests."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now)

    report = await entry.runtime_data.manager.async_plan_automatic(dry_run=True, now=now)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert report["created_request_ids"] == []
    assert report["would_create_request_ids"] == ["automatic:zone-lawn:2026-07-21T03:00:00+00:00"]
    assert stored.manual_requests == ()


async def test_replanning_reduces_then_withdraws_pending_automatic_request(
    hass: HomeAssistant,
) -> None:
    """Keep pending automatic work aligned with water delivered by other requests."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now, deficit_mm=10)
    manager = entry.runtime_data.manager
    await manager.async_plan_automatic(now=now)

    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 1},
    )
    reduced = await manager.async_plan_automatic(now=now)
    request = manager._stored_state.manual_requests[0]
    assert reduced["updated_request_ids"] == [request.request_id]
    assert request.target_value == pytest.approx(120)

    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 0},
    )
    withdrawn = await manager.async_plan_automatic(now=now)
    assert withdrawn["cancelled_request_ids"] == [request.request_id]
    assert manager._stored_state.manual_requests[0].status == "cancelled"


async def test_recalculation_keeps_all_balance_snapshot_fields_until_complete_idle(
    hass: HomeAssistant,
) -> None:
    """Do not mix persisted expert edits into an already open automatic request."""
    entry, zone = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now, deficit_mm=10)
    manager = entry.runtime_data.manager
    await manager.async_plan_automatic(now=now)
    original = manager._stored_state.manual_requests[0]

    hass.config_entries.async_update_subentry(
        entry,
        zone,
        data={
            **zone.data,
            "area_m2": 20,
            "application_efficiency": 1,
            "maximum_deficit_mm": 25,
            "minimum_effective_liters": 7,
        },
    )
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 2},
    )

    report = await manager.async_plan_automatic(now=now)
    updated = manager._stored_state.manual_requests[0]

    assert report["updated_request_ids"] == [original.request_id]
    assert updated.target_value != original.target_value
    assert (
        updated.balance_area_m2,
        updated.balance_application_efficiency,
        updated.balance_maximum_deficit_mm,
        updated.balance_minimum_effective_liters,
    ) == (10, 0.5, 50, 2)


async def test_withdrawal_can_recreate_in_same_window_but_explicit_skip_stays_suppressed(
    hass: HomeAssistant,
) -> None:
    """Distinguish recalculation withdrawal from the user's skip-once intent."""
    entry, zone = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    manager = entry.runtime_data.manager
    _make_zone_due(entry, now, deficit_mm=10)
    created = await manager.async_plan_automatic(now=now)
    request_id = created["created_request_ids"][0]

    manager._stored_state = replace(manager._stored_state, zone_deficit_mm={"zone-lawn": 0})
    await manager.async_plan_automatic(now=now)
    assert manager._request(request_id).status == "cancelled"

    manager._stored_state = replace(manager._stored_state, zone_deficit_mm={"zone-lawn": 10})
    recreated = await manager.async_plan_automatic(now=now)
    assert recreated["recreated_request_ids"] == [request_id]
    assert manager._request(request_id).status == "pending"

    await hass.services.async_call(
        DOMAIN,
        "cancel_request",
        {"config_entry_id": entry.entry_id, "request_id": request_id},
        blocking=True,
    )
    recreated_after_cancel = await manager.async_plan_automatic(now=now)
    assert recreated_after_cancel["recreated_request_ids"] == [request_id]
    assert manager._request(request_id).status == "pending"

    skip_response = await hass.services.async_call(
        DOMAIN,
        "skip_automatic",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zone.subentry_id,
            "at": now,
        },
        blocking=True,
        return_response=True,
    )
    assert skip_response["opportunity_id"] == request_id
    suppressed = await manager.async_plan_automatic(now=now)
    assert suppressed["recreated_request_ids"] == []
    assert manager._request(request_id).status == "cancelled"
    assert suppressed["zones"][0]["reason"] == "opportunity_suppressed"

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _stop_background_planning(entry)
    restarted = await entry.runtime_data.manager.async_plan_automatic(now=now)
    assert restarted["recreated_request_ids"] == []
    assert entry.runtime_data.manager._request(request_id).status == "cancelled"


async def test_outside_window_creates_no_automatic_request_but_manual_remains_allowed(
    hass: HomeAssistant,
) -> None:
    """Apply watering windows only to automatic requests."""
    entry, zone = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
    _make_zone_due(entry, now)

    report = await entry.runtime_data.manager.async_plan_automatic(now=now)
    manual = await entry.runtime_data.manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=30,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )

    assert report["created_request_ids"] == []
    assert report["zones"][0]["reason"] == "outside_watering_window"
    request = entry.runtime_data.manager._request(manual["request_id"])
    assert request is not None
    assert request.source == "manual"


async def test_finalized_weather_is_persistent_and_idempotent(hass: HomeAssistant) -> None:
    """Apply crop ET and effective rain once per finalized accounting period."""
    entry, _ = await _setup_automatic_zone(hass)
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

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert first["applied"] is True
    assert second["applied"] is False
    assert stored.zone_deficit_mm["zone-lawn"] == 3
    assert "2026-07-20" in stored.finalized_weather_periods


async def test_finalized_weather_persists_complete_zone_explanation(
    hass: HomeAssistant,
) -> None:
    """Retain the exact model contributions and target conversion used for a final day."""
    entry, _ = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager

    result = await manager.async_finalize_daily_weather(
        period_id="2026-07-20",
        reference_evapotranspiration_mm=6,
        rain_mm=30,
    )
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    snapshot = stored.weather_calculation_snapshots["2026-07-20"]
    zones = snapshot["zones"]
    assert isinstance(zones, dict)
    explanation = zones["zone-lawn"]

    assert result["applied"] is True
    assert explanation["crop_evapotranspiration_mm"] == 6
    assert explanation["effective_rain_mm"] == 6
    assert explanation["drainage_mm"] == 19
    assert explanation["runoff_mm"] == 5
    assert explanation["final_deficit_mm"] == 0
    assert explanation["target"]["gross_liters_before_limits"] == 0


async def test_forecast_rain_defers_without_reducing_balance_or_target(
    hass: HomeAssistant,
) -> None:
    """Keep forecast data in planning only and bound the delay from its first use."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now, deficit_mm=10)
    manager = entry.runtime_data.manager
    manager._rain_forecast = RainForecast(
        amount_mm=8,
        probability_percent=90,
        valid_at=now + timedelta(hours=4),
        issued_at=now,
        source="weather_entity",
        quality="forecast",
    )

    report = await manager.async_plan_automatic(now=now)

    assert report["created_request_ids"] == []
    assert report["zones"][0]["reason"] == "forecast_rain_deferred"
    assert manager._stored_state.zone_deficit_mm["zone-lawn"] == 10
    assert report["zones"][0]["target_liters"] == 100
    assert manager._stored_state.forecast_deferral_started["zone-lawn"] == now.isoformat()
    deadline = manager._stored_state.forecast_deferral_deadlines["zone-lawn"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _stop_background_planning(entry)
    manager = entry.runtime_data.manager
    assert manager._rain_forecast is None
    transient = await manager.async_plan_automatic(now=now + timedelta(minutes=5))
    assert transient["zones"][0]["reason"] == "forecast_rain_deferred"
    assert manager._stored_state.forecast_deferral_deadlines["zone-lawn"] == deadline

    manager._rain_forecast = RainForecast(
        amount_mm=1,
        probability_percent=10,
        valid_at=now + timedelta(hours=4),
        issued_at=now + timedelta(minutes=10),
        source="weather_entity",
        quality="forecast",
    )
    sub_threshold = await manager.async_plan_automatic(now=now + timedelta(minutes=10))
    assert sub_threshold["zones"][0]["reason"] == "forecast_rain_deferred"
    assert manager._stored_state.forecast_deferral_deadlines["zone-lawn"] == deadline

    after_limit = now + timedelta(hours=24, minutes=30)
    manager._rain_forecast = RainForecast(
        amount_mm=8,
        probability_percent=90,
        valid_at=after_limit + timedelta(hours=1),
        issued_at=after_limit,
        source="weather_entity",
        quality="forecast",
    )
    resumed = await manager.async_plan_automatic(now=after_limit)
    assert resumed["created_request_ids"]
    assert "zone-lawn" not in manager._stored_state.forecast_deferral_deadlines
    assert "zone-lawn" in manager._stored_state.cancelled_forecast_deferrals


async def test_forecast_deferral_explicit_cancellation_blocks_same_forecast(
    hass: HomeAssistant,
) -> None:
    """Expose an explicit cancellation path instead of inferring intent from forecast loss."""
    entry, zone = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now, deficit_mm=10)
    manager = entry.runtime_data.manager
    manager._rain_forecast = RainForecast(
        amount_mm=8,
        probability_percent=90,
        valid_at=now + timedelta(hours=4),
        issued_at=now,
        source="weather_entity",
        quality="forecast",
    )
    await manager.async_plan_automatic(now=now)

    response = await hass.services.async_call(
        DOMAIN,
        "clear_forecast_deferral",
        {"config_entry_id": entry.entry_id, "zone_subentry_id": zone.subentry_id},
        blocking=True,
        return_response=True,
    )
    planned = await manager.async_plan_automatic(now=now + timedelta(minutes=1))

    assert response["cancelled"] is True
    assert "zone-lawn" in manager._stored_state.cancelled_forecast_deferrals
    assert "zone-lawn" not in manager._stored_state.forecast_deferral_started
    assert planned["created_request_ids"]


async def test_current_day_planning_uses_provisional_not_finalized_deficit(
    hass: HomeAssistant,
) -> None:
    """Plan from today's estimate while retaining the durable final balance unchanged."""
    entry, _ = await _setup_automatic_zone(hass)
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    manager = entry.runtime_data.manager
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 2},
        zone_last_effective_irrigation={"zone-lawn": (now - timedelta(days=2)).isoformat()},
    )
    manager._zone_provisional_deficit_mm = {"zone-lawn": 8}
    manager._provisional_period_id = now.astimezone(dt_util.DEFAULT_TIME_ZONE).date().isoformat()

    report = await manager.async_plan_automatic(now=now)

    assert report["zones"][0]["target_liters"] == 100
    assert manager._stored_state.zone_deficit_mm["zone-lawn"] == 2


async def test_restart_backfills_all_retained_missing_days_once(
    hass: HomeAssistant,
) -> None:
    """Process a multi-day outage chronologically and never duplicate it after restart."""
    entry, _ = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    now = dt_util.now()
    due_day = now.date() - timedelta(days=1)
    last_day = due_day - timedelta(days=3)
    manager._installation_data.update(
        {
            "et0_sensors": ["sensor.et0"],
            "rain_sensors": ["sensor.rain"],
            "weather_backfill_days": 14,
        }
    )
    manager._stored_state = replace(
        manager._stored_state,
        finalized_weather_periods={last_day.isoformat(): "[0,0]"},
    )
    await manager._store.async_save(manager._stored_state)

    async def daily_weather(day: date, *, end: datetime | None = None) -> DailyWeather:
        period_end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        return DailyWeather(
            period_id=day.isoformat(),
            start_utc=period_end - timedelta(days=1),
            end_utc=period_end,
            minimum_temperature_c=None,
            maximum_temperature_c=None,
            mean_temperature_c=None,
            mean_humidity_percent=None,
            wind_speed_2m_m_s=None,
            solar_radiation_mj_m2_day=None,
            sunshine_duration_hours=None,
            pressure_kpa=None,
            rain_mm=WeatherValue(0, "sensor.rain", 2, period_end.isoformat(), "observed"),
            direct_et0_mm=WeatherValue(2, "sensor.et0", 1, period_end.isoformat(), "observed"),
        )

    manager._weather.async_daily_weather = AsyncMock(side_effect=daily_weather)
    finalized = await manager._async_backfill_weather_days(now, through_yesterday=True)
    assert finalized == [(last_day + timedelta(days=offset)).isoformat() for offset in (1, 2, 3)]
    assert manager._stored_state.zone_deficit_mm["zone-lawn"] == 6

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await _stop_background_planning(entry)
    restarted = entry.runtime_data.manager
    restarted._weather.async_daily_weather = AsyncMock(side_effect=daily_weather)

    assert await restarted._async_backfill_weather_days(now, through_yesterday=True) == []
    assert restarted._weather.async_daily_weather.await_count == 0
    assert restarted._stored_state.zone_deficit_mm["zone-lawn"] == 6


async def test_due_check_finalizes_after_nonexistent_dst_wall_time(
    hass: HomeAssistant,
) -> None:
    """A skipped 02:30 wall time remains due when the interval callback runs at 03:05."""
    entry, _ = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    berlin = ZoneInfo("Europe/Berlin")
    now = datetime(2026, 3, 29, 3, 5, tzinfo=berlin)
    due_day = date(2026, 3, 28)
    manager._installation_data.update(
        {
            "weather_finalization_time": "02:30:00",
            "weather_backfill_days": 2,
        }
    )
    manager.async_finalize_weather_day = AsyncMock(
        side_effect=lambda day: (
            manager._stored_state.finalized_weather_periods.update({day.isoformat(): "accounted"})
            or {"applied": True, "period_id": day.isoformat()}
        )
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", berlin):
        first = await manager._async_backfill_weather_days(now)
        second = await manager._async_backfill_weather_days(now + timedelta(minutes=15))

    assert first == [date(2026, 3, 27).isoformat(), due_day.isoformat()]
    assert second == []


async def test_seasonal_weather_fallback_is_degraded_then_expires(
    hass: HomeAssistant,
) -> None:
    """Expose bounded fallback quality and stop demand automation after its duration."""
    entry, _ = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    manager._installation_data.update(
        {
            "et0_sensors": ["sensor.et0"],
            "rain_sensors": ["sensor.rain"],
            "weather_fallback_days": 3,
            "seasonal_et0_mm": "4,4,4,4,4,4,4,4,4,4,4,4",
        }
    )
    end = datetime(2026, 7, 21, 7, tzinfo=UTC)
    weather = DailyWeather(
        period_id="2026-07-20",
        start_utc=end - timedelta(days=1),
        end_utc=end,
        minimum_temperature_c=None,
        maximum_temperature_c=None,
        mean_temperature_c=None,
        mean_humidity_percent=None,
        wind_speed_2m_m_s=None,
        solar_radiation_mj_m2_day=None,
        sunshine_duration_hours=None,
        pressure_kpa=None,
        rain_mm=WeatherValue(0, "sensor.rain", 2, end.isoformat(), "observed"),
        direct_et0_mm=None,
    )
    manager._weather.async_daily_weather = AsyncMock(return_value=weather)

    fallback = await manager.async_finalize_weather_day(date(2026, 7, 20))
    snapshot = manager._stored_state.weather_calculation_snapshots["2026-07-20"]
    assert fallback["applied"] is True
    assert snapshot["et0"]["method"] == "seasonal_fallback"
    assert snapshot["et0"]["quality"] == "degraded"

    manager._stored_state = replace(
        manager._stored_state,
        weather_failure_since=(datetime.now(UTC) - timedelta(days=4)).isoformat(),
    )
    expired = await manager.async_finalize_weather_day(date(2026, 7, 19))
    assert expired["applied"] is True
    assert expired["accounting_applied"] is False
    assert expired["quality"] == "unknown"
    assert "2026-07-19" in manager._stored_state.finalized_weather_periods
    assert (
        manager._stored_state.weather_calculation_snapshots["2026-07-19"]["reason"]
        == "fallback_duration_exhausted"
    )
    assert manager._weather_automation_available is False


async def test_delivered_automatic_water_reduces_deficit_and_resets_effective_interval(
    hass: HomeAssistant,
) -> None:
    """Account delivered automatic water in the same durable request transition."""
    entry, zone = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="automatic:test",
        sequence=1,
        zone_id="zone-lawn",
        zone_subentry_id=zone.subentry_id,
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="volume",
        target_value=20,
        remaining_value=20,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        status="executing",
        source="automatic",
        execution_id="execution-auto",
        balance_area_m2=10,
        balance_application_efficiency=0.5,
        balance_maximum_deficit_mm=50,
        balance_minimum_effective_liters=2,
    )
    execution = IrrigationExecutionState(
        execution_id="execution-auto",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type="volume",
        target_value=20,
        remaining_value=20,
        status="watering",
        created_at=now.isoformat(),
        balance_area_m2=10,
        balance_application_efficiency=0.5,
        balance_maximum_deficit_mm=50,
        balance_minimum_effective_liters=2,
    )
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 10},
        forecast_deferral_started={"zone-lawn": now.isoformat()},
        forecast_deferral_deadlines={"zone-lawn": (now + timedelta(hours=24)).isoformat()},
        cancelled_forecast_deferrals=("zone-lawn",),
        manual_requests=(request,),
        irrigation_executions=(execution,),
    )

    await manager._async_finish_dose(
        request.request_id,
        ExecutionResult(
            zone_id="zone-lawn",
            duration_seconds=120,
            delivered_liters=20,
            measurement_quality="measured",
        ),
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.zone_deficit_mm["zone-lawn"] == pytest.approx(9)
    assert "zone-lawn" not in stored.forecast_deferral_started
    assert "zone-lawn" not in stored.forecast_deferral_deadlines
    assert "zone-lawn" not in stored.cancelled_forecast_deferrals
    assert "zone-lawn" in stored.zone_last_effective_irrigation
    assert stored.manual_requests[0].status == "completed"


async def test_delivery_credit_uses_request_snapshot_after_zone_reconfiguration(
    hass: HomeAssistant,
) -> None:
    """Keep balance accounting immutable while a request is open."""
    entry, zone = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
    _make_zone_due(entry, now, deficit_mm=40)
    await manager.async_plan_automatic(now=now)
    request = manager._stored_state.manual_requests[0]
    assert request.balance_area_m2 == 10
    assert request.balance_application_efficiency == 0.5
    assert request.balance_maximum_deficit_mm == 50
    assert request.balance_minimum_effective_liters == 2

    execution = IrrigationExecutionState(
        execution_id="execution-snapshot",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type=request.target_type,
        target_value=request.target_value,
        remaining_value=request.remaining_value,
        status="watering",
        created_at=now.isoformat(),
        balance_area_m2=request.balance_area_m2,
        balance_application_efficiency=request.balance_application_efficiency,
        balance_maximum_deficit_mm=request.balance_maximum_deficit_mm,
        balance_minimum_effective_liters=request.balance_minimum_effective_liters,
    )
    request = replace(request, status="executing", execution_id=execution.execution_id)
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(execution,),
    )
    hass.config_entries.async_update_subentry(
        entry,
        zone,
        data={
            **zone.data,
            "area_m2": 100,
            "application_efficiency": 1,
            "maximum_deficit_mm": 5,
            "minimum_effective_liters": 100,
        },
    )

    await manager._async_finish_dose(
        request.request_id,
        ExecutionResult(
            zone_id=request.zone_id,
            duration_seconds=request.target_value,
            delivered_liters=20,
            measurement_quality="measured",
        ),
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.zone_deficit_mm["zone-lawn"] == pytest.approx(39)
    assert "zone-lawn" in stored.zone_last_effective_irrigation


async def test_legacy_recovery_backfills_active_snapshot_from_linked_execution(
    hass: HomeAssistant,
) -> None:
    """Credit recovered delivery from the immutable linked execution snapshot."""
    entry, zone = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="legacy-recovery",
        sequence=1,
        zone_id="zone-lawn",
        zone_subentry_id=zone.subentry_id,
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="volume",
        target_value=20,
        remaining_value=20,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        status="executing",
        execution_id="legacy-execution",
    )
    execution = IrrigationExecutionState(
        execution_id="legacy-execution",
        request_id=request.request_id,
        zone_id=request.zone_id,
        target_type=request.target_type,
        target_value=20,
        remaining_value=20,
        status="watering",
        created_at=now.isoformat(),
        balance_area_m2=10,
        balance_application_efficiency=0.5,
        balance_maximum_deficit_mm=50,
        balance_minimum_effective_liters=2,
    )
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 10},
        manual_requests=(request,),
        irrigation_executions=(execution,),
        active_execution=ActiveExecutionState(
            zone_id="zone-lawn",
            zone_valve="switch.lawn",
            main_valve=None,
            meter_raw_baseline_liters=None,
            prepared_at=now.isoformat(),
            watering_started_at=now.isoformat(),
            requested_duration_seconds=60,
            estimated_flow_l_min=60,
            requested_amount_liters=20,
            hard_time_limit_seconds=60,
            meter_failure_strategy="estimated_time_fallback",
            fallback_started_at=now.isoformat(),
            fallback_checkpoint_at=now.isoformat(),
            delivered_liters_at_fallback=20,
            request_id=request.request_id,
            execution_id=execution.execution_id,
        ),
    )

    await manager._async_recover_interrupted_execution(could_have_flowed=False)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.zone_deficit_mm["zone-lawn"] == pytest.approx(9)
    assert stored.uncredited_balance_deliveries == ()
    assert stored.irrigation_executions[0].balance_area_m2 == 10


async def test_recovery_without_trustworthy_snapshot_records_uncredited_delivery(
    hass: HomeAssistant,
) -> None:
    """Persist missing balance credit for explicit later reconciliation."""
    entry, _ = await _setup_automatic_zone(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={"zone-lawn": 10},
        active_execution=ActiveExecutionState(
            zone_id="zone-lawn",
            zone_valve="switch.lawn",
            main_valve=None,
            meter_raw_baseline_liters=None,
            prepared_at=now.isoformat(),
            watering_started_at=now.isoformat(),
            requested_duration_seconds=60,
            estimated_flow_l_min=60,
            requested_amount_liters=20,
            hard_time_limit_seconds=60,
            meter_failure_strategy="estimated_time_fallback",
            fallback_started_at=now.isoformat(),
            fallback_checkpoint_at=now.isoformat(),
            delivered_liters_at_fallback=20,
        ),
    )

    await manager._async_recover_interrupted_execution(could_have_flowed=False)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.zone_deficit_mm["zone-lawn"] == 10
    assert len(stored.uncredited_balance_deliveries) == 1
    reconciliation = stored.uncredited_balance_deliveries[0]
    assert reconciliation.zone_id == "zone-lawn"
    assert reconciliation.delivered_liters == 20
    assert reconciliation.reason == "missing_immutable_balance_snapshot"
    response = await hass.services.async_call(
        DOMAIN,
        "list_requests",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert response["uncredited_balance_deliveries"][0]["reconciliation_id"] == (
        reconciliation.reconciliation_id
    )
