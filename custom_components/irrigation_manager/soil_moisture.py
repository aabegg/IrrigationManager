"""Explicit soil-moisture validation and conservative interpretation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import fmean, median

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant


@dataclass(frozen=True, slots=True)
class SoilMoistureAssessment:
    """Validated aggregate and its explicitly configured planning effect."""

    status: str
    aggregate_percent: float | None
    valid_entities: tuple[str, ...]
    invalid_entities: tuple[str, ...]
    wet_inhibit: bool
    safety_blocked: bool
    correction_mm: float

    def as_dict(self) -> dict[str, object]:
        """Return a calculation-snapshot-safe representation."""
        return {
            "status": self.status,
            "aggregate_percent": self.aggregate_percent,
            "valid_sensor_count": len(self.valid_entities),
            "invalid_sensor_count": len(self.invalid_entities),
            "wet_inhibit": self.wet_inhibit,
            "safety_blocked": self.safety_blocked,
            "correction_mm": self.correction_mm,
        }


def assess_soil_moisture(
    hass: HomeAssistant,
    *,
    entity_ids: list[str],
    aggregation: str,
    role: str,
    max_age_seconds: float,
    wet_threshold: float,
    correction_limit_mm: float,
    now: datetime,
) -> SoilMoistureAssessment:
    """Aggregate fresh percentage sensors; invalid inputs never become ET truth."""
    values: list[float] = []
    valid: list[str] = []
    invalid: list[str] = []
    for entity_id in entity_ids:
        state = hass.states.get(entity_id)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            invalid.append(entity_id)
            continue
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        age = (now.astimezone(UTC) - state.last_reported.astimezone(UTC)).total_seconds()
        try:
            value = float(state.state)
        except ValueError:
            value = math.nan
        if (
            unit != PERCENTAGE
            or age > max_age_seconds
            or not math.isfinite(value)
            or not 0 <= value <= 100
        ):
            invalid.append(entity_id)
            continue
        valid.append(entity_id)
        values.append(value)
    if not values:
        return SoilMoistureAssessment(
            "unavailable",
            None,
            (),
            tuple(invalid),
            False,
            role == "safety_wet_inhibit",
            0.0,
        )
    if aggregation == "minimum":
        aggregate = min(values)
    elif aggregation == "mean":
        aggregate = fmean(values)
    elif aggregation == "median":
        aggregate = median(values)
    else:
        raise ValueError("Unsupported soil-moisture aggregation")
    wet = aggregate >= wet_threshold
    correction = correction_limit_mm if role == "conservative_correction" and wet else 0.0
    return SoilMoistureAssessment(
        "partial" if invalid else "valid",
        aggregate,
        tuple(valid),
        tuple(invalid),
        role == "safety_wet_inhibit" and wet,
        role == "safety_wet_inhibit" and (wet or bool(invalid)),
        correction,
    )
