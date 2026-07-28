"""Public seasonal-baseline behavior from the authoritative concept."""

from datetime import UTC, date, datetime

import pytest

from custom_components.irrigation_manager.seasonal import (
    canonical_seasonal_factors,
    resolve_seasonal_baseline,
)
from custom_components.irrigation_manager.target_resolution import (
    AutomaticTargetResolution,
    TargetResolutionOutcome,
    resolve_automatic_target,
)


def test_seasonal_baseline_interpolates_from_local_month_anchor() -> None:
    """Interpolate daily without rounding the factor or resulting target."""
    resolution = resolve_seasonal_baseline(
        base_target=600.0,
        local_date=date(2026, 1, 16),
        seasonal_module_enabled=True,
        zone_enabled=True,
        monthly_factors={
            "january": 1.0,
            "february": 2.0,
        },
    )

    assert resolution.factor == pytest.approx(1.0 + 15 / 31)
    assert resolution.seasonal_base_target == pytest.approx(600.0 * (1.0 + 15 / 31))
    assert resolution.warning is None


def test_invalid_active_curve_falls_back_visibly_to_neutral_factor() -> None:
    """A malformed comfort-module curve must not block baseline irrigation."""
    resolution = resolve_seasonal_baseline(
        base_target=600.0,
        local_date=date(2026, 7, 1),
        seasonal_module_enabled=True,
        zone_enabled=True,
        monthly_factors={"july": 0.0},
    )

    assert resolution.factor == 1.0
    assert resolution.seasonal_base_target == 600.0
    assert resolution.warning == "invalid_seasonal_curve"


def test_curve_validation_fills_neutral_months_and_rejects_excess_precision() -> None:
    """Persist a complete bounded curve even when the user changes one month."""
    factors = canonical_seasonal_factors({"january": 1.25})

    assert factors["january"] == 1.25
    assert factors["february"] == 1.0
    assert tuple(factors) == (
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    )
    with pytest.raises(ValueError, match="two decimal"):
        canonical_seasonal_factors({"january": 1.111})


@pytest.mark.parametrize(
    ("module_enabled", "zone_enabled", "fallback_strategy"),
    [
        (False, True, "seasonal_module_disabled"),
        (True, False, "zone_seasonal_disabled"),
    ],
)
def test_disabled_seasonal_scope_keeps_the_baseline(
    module_enabled: bool,
    zone_enabled: bool,
    fallback_strategy: str,
) -> None:
    """A disabled seasonal scope must remain exactly behavior-neutral."""
    resolution = resolve_automatic_target(
        base_target=600.0,
        local_date=date(2026, 7, 1),
        seasonal_module_enabled=module_enabled,
        zone_seasonal_enabled=zone_enabled,
        monthly_factors={"july": 3.0},
    )

    assert resolution.outcome is TargetResolutionOutcome.EXECUTE
    assert resolution.seasonal_factor == 1.0
    assert resolution.final_target == 600.0
    assert resolution.fallback_strategy == fallback_strategy
    assert resolution.quality == "neutral"
    assert resolution.warnings == ()


def test_invalid_curve_records_explicit_fallback_evidence() -> None:
    """The shared contract exposes fallback quality and warning details."""
    resolution = resolve_automatic_target(
        base_target=600.0,
        local_date=date(2026, 7, 1),
        seasonal_module_enabled=True,
        zone_seasonal_enabled=True,
        monthly_factors={"july": 0.0},
    )

    assert resolution.outcome is TargetResolutionOutcome.EXECUTE
    assert resolution.final_target == 600.0
    assert resolution.fallback_strategy == "base_target"
    assert resolution.quality == "fallback"
    assert resolution.warnings == ("invalid_seasonal_curve",)


def test_non_execute_target_outcomes_require_complete_reason_and_deadlines() -> None:
    """Represent skip and defer outcomes without ambiguous optional evidence."""
    common = {
        "base_target": 600.0,
        "seasonal_factor": 1.0,
        "seasonal_base_target": 600.0,
        "fallback_strategy": "none",
        "quality": "valid",
        "warnings": (),
        "seasonal_module_enabled": True,
        "zone_seasonal_enabled": True,
    }
    skipped = AutomaticTargetResolution(
        outcome=TargetResolutionOutcome.SKIP,
        final_target=None,
        reason="water_not_required",
        **common,
    )
    deferred = AutomaticTargetResolution(
        outcome=TargetResolutionOutcome.DEFER,
        final_target=None,
        reason="weather_data_temporarily_unavailable",
        defer_until=datetime(2026, 7, 28, 12, tzinfo=UTC),
        make_up_deadline=datetime(2026, 7, 29, 12, tzinfo=UTC),
        **common,
    )

    assert skipped.reason == "water_not_required"
    assert deferred.make_up_deadline == datetime(2026, 7, 29, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="requires a reason"):
        AutomaticTargetResolution(
            outcome=TargetResolutionOutcome.SKIP,
            final_target=None,
            **common,
        )
    with pytest.raises(ValueError, match="requires both fixed times"):
        AutomaticTargetResolution(
            outcome=TargetResolutionOutcome.DEFER,
            final_target=None,
            reason="weather_data_temporarily_unavailable",
            **common,
        )
