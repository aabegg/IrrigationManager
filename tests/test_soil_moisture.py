"""Behavioral tests for optional soil-moisture feedback."""

from datetime import UTC, date, datetime, timedelta

import pytest
from homeassistant.core import HomeAssistant

from custom_components.irrigation_manager.soil_moisture import (
    SoilMoistureObservation,
    observe_soil_moisture,
)
from custom_components.irrigation_manager.water_balance import (
    WateringMode,
    WeatherReading,
    WeatherZoneSettings,
    ZoneWaterBalanceState,
    clear_soil_moisture_feedback_progress,
    update_water_balance,
)


def test_zone_sensor_is_normalized_against_explicit_calibration(
    hass: HomeAssistant,
) -> None:
    """Expose a calibrated zone reading without changing any water balance."""
    hass.states.async_set(
        "sensor.lawn_soil_moisture",
        "45",
        {
            "device_class": "moisture",
            "state_class": "measurement",
            "unit_of_measurement": "%",
        },
    )
    state = hass.states.get("sensor.lawn_soil_moisture")
    assert state is not None

    observation = observe_soil_moisture(
        hass,
        [
            {
                "scope_id": "zone",
                "entity_id": "sensor.lawn_soil_moisture",
                "dry_percent": 20,
                "wet_percent": 70,
            }
        ],
        [],
        now=datetime.now(UTC),
    )

    assert observation.quality == "available"
    assert observation.reason is None
    assert observation.normalized_water_fraction == pytest.approx(0.5)
    assert observation.source_entity_ids == ("sensor.lawn_soil_moisture",)
    assert observation.observed_at == state.last_reported
    assert observation.warnings == ()


def test_invalid_or_stale_sensor_never_exposes_a_balance_value(hass: HomeAssistant) -> None:
    """Classify source failures without producing a usable normalized value."""
    attributes = {
        "device_class": "moisture",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }
    assignment = [
        {
            "scope_id": "zone",
            "entity_id": "sensor.lawn_soil_moisture",
            "dry_percent": 20,
            "wet_percent": 70,
        }
    ]
    missing = observe_soil_moisture(hass, assignment, [])
    assert missing.quality == "unavailable"
    assert missing.normalized_water_fraction is None

    hass.states.async_set("sensor.lawn_soil_moisture", "101", attributes)
    implausible = observe_soil_moisture(hass, assignment, [])
    assert implausible.quality == "implausible"
    assert implausible.normalized_water_fraction is None

    hass.states.async_set("sensor.lawn_soil_moisture", "45", attributes)
    state = hass.states.get("sensor.lawn_soil_moisture")
    assert state is not None
    stale = observe_soil_moisture(
        hass,
        assignment,
        [],
        now=state.last_reported + timedelta(hours=2, seconds=1),
    )
    assert stale.quality == "stale"
    assert stale.normalized_water_fraction is None


def test_subarea_feedback_requires_every_positive_area(hass: HomeAssistant) -> None:
    """Never infer a zone correction from only one configured subarea."""
    hass.states.async_set(
        "sensor.beds_soil_moisture",
        "50",
        {
            "device_class": "moisture",
            "state_class": "measurement",
            "unit_of_measurement": "%",
        },
    )

    observation = observe_soil_moisture(
        hass,
        [
            {
                "scope_id": "beds",
                "entity_id": "sensor.beds_soil_moisture",
                "dry_percent": 20,
                "wet_percent": 80,
            }
        ],
        [
            {"id": "beds", "name": "Beds", "area_m2": 20},
            {"id": "lawn", "name": "Lawn", "area_m2": 80},
        ],
        now=datetime.now(UTC),
    )

    assert observation.quality == "incomplete"
    assert observation.reason == "soil_moisture_scope_incomplete"
    assert observation.normalized_water_fraction is None


def test_subarea_feedback_is_area_weighted_and_reanchors_when_geometry_changes(
    hass: HomeAssistant,
) -> None:
    """Include area weights and each activation generation in the anchor signature."""
    attributes = {
        "device_class": "moisture",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }
    hass.states.async_set("sensor.beds_soil_moisture", "80", attributes)
    hass.states.async_set("sensor.lawn_soil_moisture", "20", attributes)
    assignments = [
        {
            "scope_id": "beds",
            "entity_id": "sensor.beds_soil_moisture",
            "dry_percent": 20,
            "wet_percent": 80,
        },
        {
            "scope_id": "lawn",
            "entity_id": "sensor.lawn_soil_moisture",
            "dry_percent": 20,
            "wet_percent": 80,
        },
    ]

    original = observe_soil_moisture(
        hass,
        assignments,
        [
            {"id": "beds", "area_m2": 20},
            {"id": "lawn", "area_m2": 80},
        ],
        activation_id="activation-a",
    )
    changed_geometry = observe_soil_moisture(
        hass,
        assignments,
        [
            {"id": "beds", "area_m2": 50},
            {"id": "lawn", "area_m2": 50},
        ],
        activation_id="activation-a",
    )
    reactivated = observe_soil_moisture(
        hass,
        assignments,
        [
            {"id": "beds", "area_m2": 20},
            {"id": "lawn", "area_m2": 80},
        ],
        activation_id="activation-b",
    )

    assert original.normalized_water_fraction == pytest.approx(0.2)
    assert changed_geometry.normalized_water_fraction == pytest.approx(0.5)
    assert original.calibration_signature != changed_geometry.calibration_signature
    assert original.calibration_signature != reactivated.calibration_signature


def test_two_stable_observations_apply_one_bounded_daily_correction() -> None:
    """A single reading only anchors; the confirmed reading may correct conservatively."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=3.0,
        maximum_deficit_mm=20.0,
        control_type="time",
        effective_application_rate_mm_h=10.0,
    )
    first_day = date(2026, 7, 28)
    first_time = datetime(2026, 7, 28, 8, tzinfo=UTC)
    initialized = update_water_balance(
        state=None,
        settings=settings,
        current_date=first_day,
        target_date=first_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, first_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, first_time),
    )
    assert initialized.state is not None

    current_day = first_day + timedelta(days=1)
    anchor_time = first_time + timedelta(days=1)
    anchor = update_water_balance(
        state=initialized.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, anchor_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, anchor_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=1.0,
            observed_at=anchor_time,
            calibration_signature="calibration-a",
        ),
    )
    assert anchor.state is not None
    assert anchor.state.days[-1].closing_deficit_mm == 10.0
    assert anchor.state.days[-1].soil_moisture_correction_mm == 0.0
    assert "soil_moisture_observing" in anchor.warnings

    confirmed_time = anchor_time + timedelta(minutes=30)
    corrected = update_water_balance(
        state=anchor.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, confirmed_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, confirmed_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=1.0,
            observed_at=confirmed_time,
            calibration_signature="calibration-a",
        ),
    )

    assert corrected.state is not None
    day = corrected.state.days[-1]
    assert day.closing_deficit_mm == 5.0
    assert day.soil_moisture_implied_deficit_mm == 0.0
    assert day.soil_moisture_correction_mm == -5.0
    assert corrected.final_target == 1_800.0
    assert ZoneWaterBalanceState.from_dict(corrected.state.as_dict()) == corrected.state

    malformed = corrected.state.as_dict()
    malformed_days = malformed["days"]
    assert isinstance(malformed_days, list)
    assert isinstance(malformed_days[-1], dict)
    malformed_days[-1]["soil_moisture_correction_mm"] = 50.0
    with pytest.raises(ValueError, match="correction"):
        ZoneWaterBalanceState.from_dict(malformed)

    changed_calibration = update_water_balance(
        state=corrected.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, confirmed_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, confirmed_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=1.0,
            observed_at=confirmed_time + timedelta(minutes=30),
            calibration_signature="calibration-b",
        ),
    )
    assert changed_calibration.state is not None
    assert changed_calibration.state.days[-1].soil_moisture_correction_mm == 0.0
    assert changed_calibration.state.days[-1].soil_moisture_quality == "observing"
    assert changed_calibration.state.soil_moisture_calibration_signature == "calibration-b"

    unavailable = update_water_balance(
        state=corrected.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, confirmed_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, confirmed_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="unavailable",
            reason="soil_moisture_entity_unavailable",
            normalized_water_fraction=None,
            observed_at=None,
            calibration_signature="calibration-a",
        ),
    )
    assert unavailable.state is not None
    assert unavailable.state.days[-1].closing_deficit_mm == 5.0
    assert unavailable.state.days[-1].soil_moisture_correction_mm == -5.0
    recovered = update_water_balance(
        state=unavailable.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, confirmed_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, confirmed_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=0.9,
            observed_at=confirmed_time + timedelta(minutes=30),
            calibration_signature="calibration-a",
        ),
    )
    assert recovered.state is not None
    assert recovered.state.days[-1].closing_deficit_mm == 5.0
    assert recovered.state.days[-1].soil_moisture_correction_mm == -5.0
    assert recovered.state.days[-1].soil_moisture_quality == "observing"

    reduced_settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=3.0,
        maximum_deficit_mm=8.0,
        control_type="time",
        effective_application_rate_mm_h=10.0,
    )
    reduced = update_water_balance(
        state=corrected.state,
        settings=reduced_settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, confirmed_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, confirmed_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=0.9,
            observed_at=confirmed_time + timedelta(minutes=30),
            calibration_signature="calibration-a",
        ),
    )
    assert reduced.state is not None
    assert reduced.state.days[-1].soil_moisture_correction_limit_mm == 2.0
    assert reduced.state.days[-1].soil_moisture_correction_mm == -2.0

    later_time = confirmed_time + timedelta(minutes=30)
    limited = update_water_balance(
        state=corrected.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, later_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, later_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            quality="available",
            reason=None,
            normalized_water_fraction=0.9,
            observed_at=later_time,
            calibration_signature="calibration-a",
        ),
    )
    assert limited.state is not None
    assert limited.state.days[-1].closing_deficit_mm == 5.0
    assert limited.state.days[-1].soil_moisture_correction_mm == -5.0
    assert "soil_moisture_daily_limit_reached" in limited.warnings

    disabled = update_water_balance(
        state=limited.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, later_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, later_time),
        soil_moisture_feedback_enabled=False,
    )
    assert disabled.state is not None
    assert disabled.state.days[-1].closing_deficit_mm == 10.0
    assert disabled.state.days[-1].soil_moisture_quality == "disabled"
    assert disabled.state.soil_moisture_calibration_signature is None
    cleared = clear_soil_moisture_feedback_progress(limited.state)
    restarted = ZoneWaterBalanceState.from_dict(cleared.as_dict())
    assert restarted.days[-1].closing_deficit_mm == 10.0
    assert restarted.days[-1].soil_moisture_quality == "disabled"
    assert restarted.days[-1].soil_moisture_correction_mm == 0.0
    assert not any(warning.startswith("soil_moisture_") for warning in restarted.days[-1].warnings)
    assert restarted.soil_moisture_calibration_signature is None
    assert restarted.soil_moisture_anchor_fraction is None
    assert restarted.soil_moisture_last_correction_date is None


def test_deadband_observation_does_not_consume_the_daily_correction() -> None:
    """Allow a later material, confirmed observation to use the daily allowance."""
    settings = WeatherZoneSettings(
        watering_mode=WateringMode.DEMAND,
        crop_factor=1.0,
        effective_rain_factor=1.0,
        demand_threshold_mm=3.0,
        maximum_deficit_mm=20.0,
        control_type="time",
        effective_application_rate_mm_h=10.0,
    )
    current_day = date(2026, 7, 29)
    first_time = datetime(2026, 7, 29, 8, tzinfo=UTC)
    initial = update_water_balance(
        state=None,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, first_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, first_time),
    )
    assert initial.state is not None
    anchor = update_water_balance(
        state=initial.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, first_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, first_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            "available", None, 0.5, first_time, "calibration-a"
        ),
    )
    assert anchor.state is not None
    within_deadband = update_water_balance(
        state=anchor.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, first_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, first_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            "available", None, 0.5, first_time + timedelta(minutes=30), "calibration-a"
        ),
    )
    assert within_deadband.state is not None
    assert within_deadband.state.soil_moisture_last_correction_date is None

    corrected = update_water_balance(
        state=within_deadband.state,
        settings=settings,
        current_date=current_day,
        target_date=current_day,
        seasonal_base_target=3_600,
        reference_et=WeatherReading("sensor.et", 0.0, first_time),
        precipitation_total=WeatherReading("sensor.rain", 0.0, first_time),
        soil_moisture_feedback_enabled=True,
        soil_moisture_observation=SoilMoistureObservation(
            "available", None, 0.7, first_time + timedelta(minutes=60), "calibration-a"
        ),
    )
    assert corrected.state is not None
    assert corrected.state.days[-1].soil_moisture_correction_mm == pytest.approx(-4.0)
    assert corrected.state.soil_moisture_last_correction_date == current_day.isoformat()
