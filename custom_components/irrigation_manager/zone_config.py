"""Validation helpers for the shared zone target contract."""

import math
from collections.abc import Mapping

from .const import CONF_BASE_TARGET


def positive_number(value: object) -> float | None:
    """Return one finite positive number without accepting booleans."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) and number > 0 else None


def effective_schedule_target(
    zone_data: Mapping[str, object], row: Mapping[str, object]
) -> tuple[float, bool]:
    """Resolve a weekday override or the common baseline."""
    override = positive_number(row.get("target"))
    if row.get("target") is not None and override is None:
        raise ValueError("The weekday target override must be positive")
    if override is not None:
        return override, True
    baseline = positive_number(zone_data.get(CONF_BASE_TARGET))
    if baseline is None:
        raise ValueError("The zone baseline must be positive")
    return baseline, False
