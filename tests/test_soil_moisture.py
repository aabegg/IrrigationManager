"""Behavior tests for explicit soil-moisture roles."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, State

from custom_components.irrigation_manager.soil_moisture import assess_soil_moisture


def test_wet_inhibit_uses_validated_median(hass: HomeAssistant) -> None:
    """Aggregate fresh percentage sensors and expose a safety decision."""
    hass.states.async_set("sensor.bed_one", "82", {"unit_of_measurement": PERCENTAGE})
    hass.states.async_set("sensor.bed_two", "90", {"unit_of_measurement": PERCENTAGE})

    result = assess_soil_moisture(
        hass,
        entity_ids=["sensor.bed_one", "sensor.bed_two"],
        aggregation="median",
        role="safety_wet_inhibit",
        max_age_seconds=60,
        wet_threshold=80,
        correction_limit_mm=0,
        now=datetime.now(UTC),
    )

    assert result.aggregate_percent == 86
    assert result.wet_inhibit is True
    assert result.correction_mm == 0


def test_invalid_unit_never_becomes_a_balance_correction(hass: HomeAssistant) -> None:
    """Reject ambiguous raw values rather than silently overriding ET accounting."""
    hass.states.async_set("sensor.raw_probe", "0.9", {"unit_of_measurement": "V"})

    result = assess_soil_moisture(
        hass,
        entity_ids=["sensor.raw_probe"],
        aggregation="mean",
        role="conservative_correction",
        max_age_seconds=60,
        wet_threshold=80,
        correction_limit_mm=5,
        now=datetime.now(UTC),
    )

    assert result.status == "unavailable"
    assert result.aggregate_percent is None
    assert result.correction_mm == 0


def test_one_invalid_safety_sensor_blocks_even_when_other_sensor_is_dry(
    hass: HomeAssistant,
) -> None:
    """Never let a partial safety aggregate conceal an unavailable wet probe."""
    hass.states.async_set("sensor.valid_probe", "20", {"unit_of_measurement": PERCENTAGE})
    hass.states.async_set("sensor.invalid_probe", "unknown", {"unit_of_measurement": PERCENTAGE})

    result = assess_soil_moisture(
        hass,
        entity_ids=["sensor.valid_probe", "sensor.invalid_probe"],
        aggregation="minimum",
        role="safety_wet_inhibit",
        max_age_seconds=60,
        wet_threshold=80,
        correction_limit_mm=0,
        now=datetime.now(UTC),
    )

    assert result.status == "partial"
    assert result.wet_inhibit is False
    assert result.safety_blocked is True


def test_partial_correction_sensor_set_degrades_without_blocking(
    hass: HomeAssistant,
) -> None:
    """Keep non-safety roles explicit while using only valid correction observations."""
    hass.states.async_set("sensor.valid_probe", "90", {"unit_of_measurement": PERCENTAGE})
    hass.states.async_set("sensor.invalid_probe", "unknown", {"unit_of_measurement": PERCENTAGE})

    result = assess_soil_moisture(
        hass,
        entity_ids=["sensor.valid_probe", "sensor.invalid_probe"],
        aggregation="median",
        role="conservative_correction",
        max_age_seconds=60,
        wet_threshold=80,
        correction_limit_mm=4,
        now=datetime.now(UTC),
    )

    assert result.status == "partial"
    assert result.safety_blocked is False
    assert result.correction_mm == 4


def test_one_stale_safety_sensor_blocks_fresh_aggregate(hass: HomeAssistant) -> None:
    """Treat stale safety evidence as unknown even when another probe is fresh."""
    now = datetime.now(UTC)
    fresh = State(
        "sensor.fresh_probe",
        "20",
        {"unit_of_measurement": PERCENTAGE},
        last_changed=now,
        last_reported=now,
        last_updated=now,
    )
    stale_at = now - timedelta(hours=2)
    stale = State(
        "sensor.stale_probe",
        "20",
        {"unit_of_measurement": PERCENTAGE},
        last_changed=stale_at,
        last_reported=stale_at,
        last_updated=stale_at,
    )
    states = {fresh.entity_id: fresh, stale.entity_id: stale}

    with patch(
        "homeassistant.core.StateMachine.get",
        autospec=True,
        side_effect=lambda _state_machine, entity_id: states.get(entity_id),
    ):
        result = assess_soil_moisture(
            hass,
            entity_ids=[fresh.entity_id, stale.entity_id],
            aggregation="minimum",
            role="safety_wet_inhibit",
            max_age_seconds=60,
            wet_threshold=80,
            correction_limit_mm=0,
            now=now,
        )

    assert result.status == "partial"
    assert result.safety_blocked is True
