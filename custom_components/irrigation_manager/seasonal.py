"""Seasonal baseline resolution for automatic irrigation orders."""

import calendar
import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date

MONTHS = (
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
MIN_SEASONAL_FACTOR = 0.10
MAX_SEASONAL_FACTOR = 3.00
DEFAULT_SEASONAL_FACTOR = 1.00


@dataclass(frozen=True, slots=True)
class SeasonalBaselineResolution:
    """Immutable seasonal baseline input and result for one automatic order."""

    base_target: float
    factor: float
    seasonal_base_target: float
    seasonal_module_enabled: bool
    zone_enabled: bool
    warning: str | None = None


def _configured_factor(monthly_factors: Mapping[str, object], month_index: int) -> float:
    value = monthly_factors.get(MONTHS[month_index], DEFAULT_SEASONAL_FACTOR)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Seasonal factors must be numeric")
    factor = float(value)
    if not math.isfinite(factor) or not MIN_SEASONAL_FACTOR <= factor <= MAX_SEASONAL_FACTOR:
        raise ValueError("Seasonal factors must be between 0.10 and 3.00")
    if round(factor, 2) != factor:
        raise ValueError("Seasonal factors may have at most two decimal places")
    return factor


def canonical_seasonal_factors(
    monthly_factors: Mapping[str, object],
) -> dict[str, float]:
    """Validate and complete one persisted twelve-month curve."""
    unknown = set(monthly_factors) - set(MONTHS)
    if unknown:
        raise ValueError("Seasonal curve contains unknown months")
    return {month: _configured_factor(monthly_factors, index) for index, month in enumerate(MONTHS)}


def resolve_seasonal_baseline(
    *,
    base_target: float,
    local_date: date,
    seasonal_module_enabled: bool,
    zone_enabled: bool,
    monthly_factors: Mapping[str, object],
) -> SeasonalBaselineResolution:
    """Resolve one baseline through the configured local-date seasonal curve."""
    if not seasonal_module_enabled or not zone_enabled:
        return SeasonalBaselineResolution(
            base_target=base_target,
            factor=DEFAULT_SEASONAL_FACTOR,
            seasonal_base_target=base_target,
            seasonal_module_enabled=seasonal_module_enabled,
            zone_enabled=zone_enabled,
        )

    try:
        curve = canonical_seasonal_factors(monthly_factors)
    except TypeError, ValueError:
        return SeasonalBaselineResolution(
            base_target=base_target,
            factor=DEFAULT_SEASONAL_FACTOR,
            seasonal_base_target=base_target,
            seasonal_module_enabled=True,
            zone_enabled=True,
            warning="invalid_seasonal_curve",
        )
    current_index = local_date.month - 1
    next_index = (current_index + 1) % len(MONTHS)
    current = curve[MONTHS[current_index]]
    following = curve[MONTHS[next_index]]
    days_in_month = calendar.monthrange(local_date.year, local_date.month)[1]
    progress = (local_date.day - 1) / days_in_month
    factor = current + (following - current) * progress
    return SeasonalBaselineResolution(
        base_target=base_target,
        factor=factor,
        seasonal_base_target=base_target * factor,
        seasonal_module_enabled=True,
        zone_enabled=True,
    )
