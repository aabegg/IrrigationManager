"""Behavior tests for cumulative water-meter normalization."""

import pytest

from custom_components.irrigation_manager.meter import (
    CumulativeMeter,
    ImplausibleMeterRegressionError,
    round_target_to_resolution,
)


def test_meter_keeps_total_across_source_reset() -> None:
    """Continue the internal total when an ESPHome source starts from zero."""
    meter = CumulativeMeter.start(raw_liters=8_488.0)

    meter = meter.update(raw_liters=8_490.0)
    meter = meter.update(raw_liters=3.0)

    assert meter.total_liters == 8_493.0
    assert meter.reset_count == 1


def test_meter_correction_changes_displayed_total_without_rewriting_consumption() -> None:
    """Apply a physical meter correction only to current and future display."""
    meter = CumulativeMeter.start(raw_liters=1_250.0)
    corrected = meter.correct(physical_total_liters=1_300.0)

    advanced = corrected.update(raw_liters=1_260.0)

    assert corrected.accumulated_liters == 1_250.0
    assert corrected.total_liters == 1_300.0
    assert advanced.accumulated_liters == 1_260.0
    assert advanced.total_liters == 1_310.0


def test_meter_rejects_ambiguous_small_regression_without_advancing_baseline() -> None:
    """Do not convert an ordinary backwards sample into reset consumption."""
    meter = CumulativeMeter.start(raw_liters=100)

    with pytest.raises(ImplausibleMeterRegressionError):
        meter.update(raw_liters=99)

    advanced = meter.update(raw_liters=101)
    assert advanced.total_liters == 101
    assert advanced.reset_count == 0


def test_volume_target_rounds_up_to_observable_meter_resolution() -> None:
    """Never present a sub-pulse target as exactly measurable."""
    rounded = round_target_to_resolution(10.1, 0.25)

    assert rounded.target_liters == 10.25
    assert rounded.direction == "up"
    assert rounded.error_liters == pytest.approx(0.15)
