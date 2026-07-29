"""Behavioral tests for persistent weather-based target resolution."""

from datetime import UTC, date, datetime

import pytest

from custom_components.irrigation_manager.models import StoredInstallationState
from custom_components.irrigation_manager.storage import STORAGE_MINOR_VERSION, _StateStore
from custom_components.irrigation_manager.water_balance import (
    IrrigationContribution,
    WateringMode,
    WeatherReading,
    WeatherZoneSettings,
    ZoneWaterBalanceState,
    update_water_balance,
)


def test_first_weather_day_preserves_seasonal_target_and_initializes_balance() -> None:
    """Activation must not immediately reduce an established automatic target."""
    result = update_water_balance(
        state=None,
        settings=WeatherZoneSettings(
            watering_mode=WateringMode.DEMAND,
            crop_factor=1.0,
            effective_rain_factor=1.0,
            demand_threshold_mm=1.0,
            maximum_deficit_mm=100.0,
            control_type="time",
            effective_application_rate_mm_h=12.0,
        ),
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    assert result.outcome == "execute"
    assert result.final_target == 1800.0
    assert result.fallback_strategy == "water_balance_initializing"
    assert result.quality == "fallback"
    assert result.state.ready_from_date == "2026-07-29"
    assert result.state.days[-1].opening_deficit_mm == 6.0
    assert result.state.days[-1].plant_evapotranspiration_mm == 4.0
    assert result.state.days[-1].measured_precipitation_mm == 0.0
    assert result.state.days[-1].closing_deficit_mm == 10.0


def test_next_day_uses_measured_rain_and_evapotranspiration_for_time_target() -> None:
    """A complete next day converts the resulting deficit into valve-open seconds."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=0.5,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    result = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=3.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=22.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
    )

    assert result.outcome == "execute"
    assert result.final_target == 3600.0
    assert result.fallback_strategy == "none"
    assert result.quality == "valid"
    assert len(result.state.days) == 2
    assert result.state.days[-1].opening_deficit_mm == 10.0
    assert result.state.days[-1].plant_evapotranspiration_mm == 3.0
    assert result.state.days[-1].measured_precipitation_mm == 2.0
    assert result.state.days[-1].effective_precipitation_mm == 1.0
    assert result.state.days[-1].closing_deficit_mm == 12.0


def test_demand_mode_skips_when_measured_balance_is_below_threshold() -> None:
    """A due date is only an opportunity when the measured deficit is too small."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    result = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=0.5,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=30.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
    )

    assert result.outcome == "skip"
    assert result.final_target is None
    assert result.reason == "water_deficit_below_threshold"
    assert result.state.days[-1].closing_deficit_mm == 0.5


def test_minimum_mode_keeps_volume_seasonal_baseline_after_sufficient_rain() -> None:
    """Minimum watering never reduces a liter target below its seasonal baseline."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.MINIMUM,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="volume",
        irrigated_area_m2=100.0,
        irrigation_efficiency=0.8,
    )
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1000.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=0.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    result = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1000.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=0.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=28.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
    )

    assert result.outcome == "execute"
    assert result.final_target == 1000.0
    assert result.state.days[-1].closing_deficit_mm == 0.0


def test_missing_weather_sources_fall_back_without_creating_balance_state() -> None:
    """Missing comfort data must leave the established seasonal target usable."""
    result = update_water_balance(
        state=None,
        settings=WeatherZoneSettings(
            watering_mode=WateringMode.DEMAND,
            crop_factor=1.0,
            effective_rain_factor=1.0,
            demand_threshold_mm=1.0,
            maximum_deficit_mm=100.0,
            control_type="time",
            effective_application_rate_mm_h=12.0,
        ),
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=None,
        precipitation_total=None,
    )

    assert result.state is None
    assert result.outcome == "execute"
    assert result.final_target == 1800.0
    assert result.fallback_strategy == "weather_sources_unavailable"
    assert result.quality == "fallback"
    assert result.warnings == ("weather_sources_unavailable",)


def test_rain_source_change_reinitializes_without_reducing_target() -> None:
    """Unknown rainfall across a source change requires a fresh observation day."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    result = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=3.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.replacement_rain_total",
            value=2.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
    )

    assert result.outcome == "execute"
    assert result.final_target == 1800.0
    assert result.fallback_strategy == "water_balance_reinitializing"
    assert result.warnings == ("precipitation_source_changed",)
    assert result.state is not None
    assert result.state.ready_from_date == "2026-07-30"
    assert result.state.rain_source_entity_id == "sensor.replacement_rain_total"


def test_same_day_updates_replace_et_and_do_not_double_count_rain() -> None:
    """Hourly replanning may revise a day but must remain idempotent."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 12, tzinfo=UTC),
        ),
    )
    updated = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=5.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=21.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )
    repeated = update_water_balance(
        state=updated.state,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=5.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=21.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    assert repeated.state is not None
    assert len(repeated.state.days) == 1
    assert repeated.state.days[-1].reference_evapotranspiration_mm == 5.0
    assert repeated.state.days[-1].measured_precipitation_mm == 1.0
    assert repeated.state.days[-1].closing_deficit_mm == 10.0


def test_completed_time_irrigation_is_credited_once_by_execution_id() -> None:
    """Replanning after completion must not subtract the same watering twice."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    first = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )
    second = update_water_balance(
        state=first.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=3.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=21.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
    )
    contribution = IrrigationContribution(
        execution_id="execution-1",
        local_date=date(2026, 7, 29),
        target_type="duration",
        measurement_quality="unavailable",
        delivered_liters=0.0,
        delivered_duration_seconds=1800.0,
    )
    credited = update_water_balance(
        state=second.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=3.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=21.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        irrigation_contributions=(contribution,),
    )
    repeated = update_water_balance(
        state=credited.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=3.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=21.0,
            observed_at=datetime(2026, 7, 29, 18, tzinfo=UTC),
        ),
        irrigation_contributions=(contribution,),
    )

    assert repeated.state is not None
    assert repeated.state.days[-1].effective_irrigation_mm == 6.0
    assert repeated.state.days[-1].closing_deficit_mm == 6.0
    assert repeated.final_target == 1800.0
    assert repeated.state.processed_execution_ids == ("execution-1",)


def test_previous_day_irrigation_is_recovered_before_advancing_after_restart() -> None:
    """A restart between execution persistence and replanning must not lose delivered water."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    first = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
    )
    second = update_water_balance(
        state=first.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 3.0, datetime(2026, 7, 29, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 21.0, datetime(2026, 7, 29, 18, tzinfo=UTC)
        ),
    )
    result = update_water_balance(
        state=second.state,
        settings=settings,
        current_date=date(2026, 7, 30),
        target_date=date(2026, 7, 30),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 2.0, datetime(2026, 7, 30, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 21.0, datetime(2026, 7, 30, 18, tzinfo=UTC)
        ),
        irrigation_contributions=(
            IrrigationContribution(
                execution_id="late-execution",
                local_date=date(2026, 7, 29),
                target_type="duration",
                measurement_quality="unavailable",
                delivered_liters=0.0,
                delivered_duration_seconds=1800.0,
            ),
        ),
    )

    assert result.state is not None
    assert result.state.days[-2].effective_irrigation_mm == 6.0
    assert result.state.days[-2].closing_deficit_mm == 6.0
    assert result.state.days[-1].opening_deficit_mm == 6.0
    assert result.state.days[-1].closing_deficit_mm == 8.0
    assert result.state.processed_execution_ids == ("late-execution",)


def test_duplicate_execution_segment_is_credited_exactly_once() -> None:
    """One stable execution/date marker must deduplicate duplicate input records."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
    )
    contribution = IrrigationContribution(
        execution_id="duplicate",
        local_date=date(2026, 7, 29),
        target_type="duration",
        measurement_quality="unavailable",
        delivered_liters=0.0,
        delivered_duration_seconds=1800.0,
    )

    result = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 3.0, datetime(2026, 7, 29, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 29, 12, tzinfo=UTC)
        ),
        irrigation_contributions=(contribution, contribution),
    )

    assert result.state is not None
    assert result.state.days[-1].effective_irrigation_mm == 6.0
    assert result.state.processed_execution_ids == ("duplicate",)


def test_unknown_volume_delivery_forces_visible_reinitialization() -> None:
    """An unavailable meter value is not a reliable zero-liter contribution."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="volume",
        irrigated_area_m2=100.0,
        irrigation_efficiency=0.8,
    )
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=500.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
    )

    result = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=500.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 3.0, datetime(2026, 7, 29, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 29, 12, tzinfo=UTC)
        ),
        irrigation_contributions=(
            IrrigationContribution(
                execution_id="unknown-volume",
                local_date=date(2026, 7, 29),
                target_type="volume",
                measurement_quality="unavailable",
                delivered_liters=0.0,
                delivered_duration_seconds=300.0,
            ),
        ),
    )

    assert result.state is not None
    assert result.final_target == 500.0
    assert result.fallback_strategy == "water_balance_reinitializing"
    assert result.warnings == ("irrigation_delivery_unavailable",)
    assert result.state.processed_execution_ids == ("unknown-volume",)
    assert result.state.unreliable_execution_ids == ("unknown-volume",)

    recovered = update_water_balance(
        state=result.state,
        settings=settings,
        current_date=date(2026, 7, 30),
        target_date=date(2026, 7, 30),
        seasonal_base_target=500.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 2.0, datetime(2026, 7, 30, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 30, 12, tzinfo=UTC)
        ),
        irrigation_contributions=(
            IrrigationContribution(
                execution_id="unknown-volume",
                local_date=date(2026, 7, 29),
                target_type="volume",
                measurement_quality="unavailable",
                delivered_liters=0.0,
                delivered_duration_seconds=300.0,
            ),
        ),
    )

    assert recovered.fallback_strategy == "none"
    assert recovered.quality == "valid"
    assert recovered.state is not None
    assert recovered.state.unreliable_execution_ids == ("unknown-volume",)


def test_balance_state_round_trips_for_restart_recovery() -> None:
    """Persisted source progress and idempotency markers survive a restart."""
    result = update_water_balance(
        state=None,
        settings=WeatherZoneSettings(
            watering_mode=WateringMode.DEMAND,
            crop_factor=1.0,
            effective_rain_factor=1.0,
            demand_threshold_mm=1.0,
            maximum_deficit_mm=100.0,
            control_type="time",
            effective_application_rate_mm_h=12.0,
        ),
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            source_entity_id="sensor.reference_et",
            value=4.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
        precipitation_total=WeatherReading(
            source_entity_id="sensor.rain_total",
            value=20.0,
            observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
        ),
    )

    assert result.state is not None
    assert ZoneWaterBalanceState.from_dict(result.state.as_dict()) == result.state


def test_installation_storage_keeps_zone_balances_across_restart() -> None:
    """The installation storage seam owns every zone's persistent balance."""
    balance = ZoneWaterBalanceState(
        ready_from_date="2026-07-29",
        rain_source_entity_id="sensor.rain_total",
        rain_total_mm=20.0,
        rain_observed_at="2026-07-28T18:00:00+00:00",
        days=(
            update_water_balance(
                state=None,
                settings=WeatherZoneSettings(
                    watering_mode=WateringMode.DEMAND,
                    crop_factor=1.0,
                    effective_rain_factor=1.0,
                    demand_threshold_mm=1.0,
                    maximum_deficit_mm=100.0,
                    control_type="time",
                    effective_application_rate_mm_h=12.0,
                ),
                current_date=date(2026, 7, 28),
                target_date=date(2026, 7, 28),
                seasonal_base_target=1800.0,
                reference_et=WeatherReading(
                    source_entity_id="sensor.reference_et",
                    value=4.0,
                    observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
                ),
                precipitation_total=WeatherReading(
                    source_entity_id="sensor.rain_total",
                    value=20.0,
                    observed_at=datetime(2026, 7, 28, 18, tzinfo=UTC),
                ),
            ).state.days[-1],
        ),
    )
    stored = StoredInstallationState.from_dict(
        {"zone_water_balances": {"zone-1": balance.as_dict()}}
    )

    assert stored.zone_water_balances == {"zone-1": balance}
    assert StoredInstallationState.from_dict(stored.as_dict()) == stored


async def test_stage4_storage_migration_adds_empty_zone_balances() -> None:
    """Older runtime state gains no invented weather history or deficit."""
    old_state = StoredInstallationState(installation_total_liters=42.0).as_dict()
    old_state.pop("zone_water_balances")

    migrated = await _StateStore._async_migrate_func(  # type: ignore[arg-type]
        None, 2, 2, old_state
    )

    assert STORAGE_MINOR_VERSION == 4
    assert migrated["installation_total_liters"] == 42.0
    assert migrated["zone_water_balances"] == {}


def test_one_corrupt_zone_balance_cannot_prevent_runtime_state_recovery() -> None:
    """Weather history is optional and must never take down the irrigation manager."""
    state = StoredInstallationState.from_dict(
        {
            "installation_total_liters": 42.0,
            "zone_water_balances": {
                "zone-bad": {"ready_from_date": "not-a-date"},
            },
        }
    )

    assert state.installation_total_liters == 42.0
    assert state.zone_water_balances == {}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"crop_factor": 0.0}, "crop factor"),
        ({"effective_rain_factor": 1.1}, "rain factor"),
        ({"maximum_deficit_mm": 1.0, "demand_threshold_mm": 1.0}, "deficit"),
        ({"effective_application_rate_mm_h": None}, "application rate"),
    ],
)
def test_weather_settings_reject_unsafe_physical_contracts(
    change: dict[str, object], message: str
) -> None:
    """Invalid conversion values must fail at the deep module boundary."""
    values: dict[str, object] = {
        "watering_mode": WateringMode.DEMAND,
        "crop_factor": 1.0,
        "effective_rain_factor": 1.0,
        "demand_threshold_mm": 1.0,
        "maximum_deficit_mm": 100.0,
        "control_type": "time",
        "effective_application_rate_mm_h": 12.0,
    }
    values.update(change)

    with pytest.raises(ValueError, match=message):
        WeatherZoneSettings(**values)  # type: ignore[arg-type]


def test_observations_from_another_local_day_use_seasonal_fallback() -> None:
    """A stale daily total cannot be silently assigned to today's balance."""
    result = update_water_balance(
        state=None,
        settings=WeatherZoneSettings(
            watering_mode=WateringMode.DEMAND,
            crop_factor=1.0,
            effective_rain_factor=1.0,
            demand_threshold_mm=1.0,
            maximum_deficit_mm=100.0,
            control_type="time",
            effective_application_rate_mm_h=12.0,
        ),
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
    )

    assert result.state is None
    assert result.final_target == 1800.0
    assert result.fallback_strategy == "weather_observations_not_current"
    assert result.warnings == ("weather_observations_not_current",)


def test_gap_in_daily_observations_reinitializes_without_guessing_missing_weather() -> None:
    """Missing whole days must never be reconstructed from one cumulative delta."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
    )
    result = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=date(2026, 7, 30),
        target_date=date(2026, 7, 30),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 3.0, datetime(2026, 7, 30, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 24.0, datetime(2026, 7, 30, 18, tzinfo=UTC)
        ),
    )

    assert result.final_target == 1800.0
    assert result.fallback_strategy == "water_balance_reinitializing"
    assert result.warnings == ("water_balance_observation_gap",)
    assert result.state is not None
    assert result.state.ready_from_date == "2026-07-31"


def test_next_day_cumulative_rain_reset_counts_only_new_counter_value() -> None:
    """A known day boundary makes a reset usable without inventing the lost total."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
    )
    result = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=date(2026, 7, 29),
        target_date=date(2026, 7, 29),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 1.0, datetime(2026, 7, 29, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 2.0, datetime(2026, 7, 29, 18, tzinfo=UTC)
        ),
    )

    assert result.state is not None
    assert result.state.days[-1].measured_precipitation_mm == 2.0
    assert result.state.days[-1].closing_deficit_mm == 9.0
    assert result.warnings == ("precipitation_counter_reset",)


def test_same_day_cumulative_rain_regression_reinitializes_safely() -> None:
    """A mid-day counter reset has an unknown delta and therefore cannot be applied."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=1.0,
        maximum_deficit_mm=100.0,
        control_type="time",
        effective_application_rate_mm_h=12.0,
    )
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 4.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 20.0, datetime(2026, 7, 28, 12, tzinfo=UTC)
        ),
    )
    result = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=date(2026, 7, 28),
        target_date=date(2026, 7, 28),
        seasonal_base_target=1800.0,
        reference_et=WeatherReading(
            "sensor.reference_et", 5.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
        precipitation_total=WeatherReading(
            "sensor.rain_total", 1.0, datetime(2026, 7, 28, 18, tzinfo=UTC)
        ),
    )

    assert result.final_target == 1800.0
    assert result.fallback_strategy == "water_balance_reinitializing"
    assert result.warnings == ("precipitation_counter_reset",)
