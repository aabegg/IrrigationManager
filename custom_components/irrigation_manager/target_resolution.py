"""Shared automatic irrigation target-resolution contract."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from .seasonal import resolve_seasonal_baseline


class TargetResolutionOutcome(StrEnum):
    """Closed set of outcomes produced by automatic target resolution."""

    EXECUTE = "execute"
    SKIP = "skip"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class AutomaticTargetResolution:
    """Immutable explanation of the target selected for one automatic order."""

    outcome: TargetResolutionOutcome
    base_target: float
    seasonal_factor: float
    seasonal_base_target: float
    final_target: float | None
    fallback_strategy: str
    quality: str
    warnings: tuple[str, ...]
    seasonal_module_enabled: bool
    zone_seasonal_enabled: bool
    reason: str | None = None
    defer_until: datetime | None = None
    make_up_deadline: datetime | None = None

    def __post_init__(self) -> None:
        """Reject incomplete or contradictory outcome data."""
        if self.outcome is TargetResolutionOutcome.EXECUTE:
            if self.final_target is None:
                raise ValueError("Execute target resolution requires a final target")
            if self.reason is not None or self.defer_until is not None:
                raise ValueError("Execute target resolution cannot carry a deferral")
            if self.make_up_deadline is not None:
                raise ValueError("Execute target resolution cannot carry a make-up deadline")
            return
        if not self.reason:
            raise ValueError("Non-execute target resolution requires a reason")
        if self.final_target is not None:
            raise ValueError("Non-execute target resolution cannot carry a final target")
        if self.outcome is TargetResolutionOutcome.SKIP:
            if self.defer_until is not None or self.make_up_deadline is not None:
                raise ValueError("Skip target resolution cannot carry deferral times")
            return
        if self.defer_until is None or self.make_up_deadline is None:
            raise ValueError("Defer target resolution requires both fixed times")
        if self.defer_until.tzinfo is None or self.make_up_deadline.tzinfo is None:
            raise ValueError("Defer target resolution times must be timezone-aware")
        if self.make_up_deadline < self.defer_until:
            raise ValueError("Make-up deadline cannot precede defer-until time")


def resolve_automatic_target(
    *,
    base_target: float,
    local_date: date,
    seasonal_module_enabled: bool,
    zone_seasonal_enabled: bool,
    monthly_factors: Mapping[str, object],
) -> AutomaticTargetResolution:
    """Resolve the current automatic target and capture its decision evidence."""
    seasonal = resolve_seasonal_baseline(
        base_target=base_target,
        local_date=local_date,
        seasonal_module_enabled=seasonal_module_enabled,
        zone_enabled=zone_seasonal_enabled,
        monthly_factors=monthly_factors,
    )
    warnings = (seasonal.warning,) if seasonal.warning is not None else ()
    if warnings:
        fallback_strategy = "base_target"
        quality = "fallback"
    elif not seasonal.seasonal_module_enabled:
        fallback_strategy = "seasonal_module_disabled"
        quality = "neutral"
    elif not seasonal.zone_enabled:
        fallback_strategy = "zone_seasonal_disabled"
        quality = "neutral"
    else:
        fallback_strategy = "none"
        quality = "valid"
    return AutomaticTargetResolution(
        outcome=TargetResolutionOutcome.EXECUTE,
        base_target=seasonal.base_target,
        seasonal_factor=seasonal.factor,
        seasonal_base_target=seasonal.seasonal_base_target,
        final_target=seasonal.seasonal_base_target,
        fallback_strategy=fallback_strategy,
        quality=quality,
        warnings=warnings,
        seasonal_module_enabled=seasonal.seasonal_module_enabled,
        zone_seasonal_enabled=seasonal.zone_enabled,
    )
