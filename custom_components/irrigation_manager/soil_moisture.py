"""Calibrated and conservative soil-moisture observation contract."""

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

MAX_SOIL_MOISTURE_AGE = timedelta(hours=2)
MIN_CALIBRATION_SPAN_PERCENT = 5.0


@dataclass(frozen=True, slots=True)
class SoilMoistureReading:
    """One calibrated source reading used by the aggregate."""

    scope_id: str
    source_entity_id: str
    raw_percent: float
    normalized_water_fraction: float
    observed_at: datetime
    weight: float
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible diagnostics representation."""
        result = asdict(self)
        result["observed_at"] = self.observed_at.isoformat()
        result["warnings"] = list(self.warnings)
        return result


@dataclass(frozen=True, slots=True)
class SoilMoistureObservation:
    """One complete zone-level feedback observation."""

    quality: str
    reason: str | None
    normalized_water_fraction: float | None
    observed_at: datetime | None
    calibration_signature: str | None
    readings: tuple[SoilMoistureReading, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def source_entity_ids(self) -> tuple[str, ...]:
        """Return the explicit source identities for redaction and diagnostics."""
        return tuple(reading.source_entity_id for reading in self.readings)

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible diagnostics representation."""
        return {
            "quality": self.quality,
            "reason": self.reason,
            "normalized_water_fraction": self.normalized_water_fraction,
            "observed_at": None if self.observed_at is None else self.observed_at.isoformat(),
            "calibration_signature": self.calibration_signature,
            "source_entity_ids": list(self.source_entity_ids),
            "readings": [reading.as_dict() for reading in self.readings],
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class _Assignment:
    scope_id: str
    entity_id: str
    dry_percent: float
    wet_percent: float
    weight: float


def _invalid(reason: str) -> SoilMoistureObservation:
    return SoilMoistureObservation(
        quality="incomplete",
        reason=reason,
        normalized_water_fraction=None,
        observed_at=None,
        calibration_signature=None,
    )


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _assignments(
    configured: object, subareas: object
) -> tuple[tuple[_Assignment, ...], str | None]:
    if not isinstance(configured, list) or not configured:
        return (), "soil_moisture_not_configured"
    if not all(isinstance(item, Mapping) for item in configured):
        return (), "soil_moisture_configuration_invalid"
    raw_subareas: Sequence[Mapping[object, object]] = (
        tuple(item for item in subareas if isinstance(item, Mapping))
        if isinstance(subareas, list)
        else ()
    )
    area_by_id: dict[str, float] = {}
    for item in raw_subareas:
        scope_id = item.get("id")
        area = _number(item.get("area_m2"))
        if isinstance(scope_id, str) and scope_id and area is not None and area > 0:
            area_by_id[scope_id] = area

    parsed: list[_Assignment] = []
    scopes: set[str] = set()
    for item in configured:
        scope_id = item.get("scope_id")
        entity_id = item.get("entity_id")
        dry = _number(item.get("dry_percent"))
        wet = _number(item.get("wet_percent"))
        if (
            not isinstance(scope_id, str)
            or not scope_id
            or scope_id in scopes
            or not isinstance(entity_id, str)
            or not entity_id.startswith("sensor.")
            or dry is None
            or wet is None
            or not 0 <= dry <= 95
            or not 5 <= wet <= 100
            or wet - dry < MIN_CALIBRATION_SPAN_PERCENT
        ):
            return (), "soil_moisture_configuration_invalid"
        scopes.add(scope_id)
        parsed.append(
            _Assignment(
                scope_id=scope_id,
                entity_id=entity_id,
                dry_percent=dry,
                wet_percent=wet,
                weight=1.0 if scope_id == "zone" else area_by_id.get(scope_id, 0.0),
            )
        )
    if scopes == {"zone"}:
        return tuple(parsed), None
    if "zone" in scopes or not area_by_id or scopes != set(area_by_id):
        return (), "soil_moisture_scope_incomplete"
    if any(item.weight <= 0 for item in parsed):
        return (), "soil_moisture_scope_incomplete"
    return tuple(parsed), None


def _signature(assignments: tuple[_Assignment, ...], activation_id: object) -> str:
    canonical = {
        "activation_id": activation_id if isinstance(activation_id, str) else None,
        "assignments": [
            {
                "scope_id": item.scope_id,
                "entity_id": item.entity_id,
                "dry_percent": item.dry_percent,
                "wet_percent": item.wet_percent,
                "weight": item.weight,
            }
            for item in sorted(assignments, key=lambda item: item.scope_id)
        ],
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def observe_soil_moisture(
    hass: HomeAssistant,
    configured_assignments: object,
    subareas: object,
    *,
    activation_id: object = None,
    now: datetime | None = None,
) -> SoilMoistureObservation:
    """Normalize one complete zone or subarea sensor assignment."""
    assignments, error = _assignments(configured_assignments, subareas)
    if error is not None:
        return _invalid(error)
    evaluated_at = (now or datetime.now(UTC)).astimezone(UTC)
    readings: list[SoilMoistureReading] = []
    all_warnings: list[str] = []
    for assignment in assignments:
        state = hass.states.get(assignment.entity_id)
        if state is None:
            return SoilMoistureObservation(
                quality="unavailable",
                reason="soil_moisture_entity_not_found",
                normalized_water_fraction=None,
                observed_at=None,
                calibration_signature=_signature(assignments, activation_id),
            )
        if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            return SoilMoistureObservation(
                quality="unavailable",
                reason="soil_moisture_entity_unavailable",
                normalized_water_fraction=None,
                observed_at=None,
                calibration_signature=_signature(assignments, activation_id),
            )
        if (
            state.attributes.get("device_class") != "moisture"
            or state.attributes.get("state_class") != "measurement"
            or state.attributes.get("unit_of_measurement") != "%"
        ):
            return SoilMoistureObservation(
                quality="incomplete",
                reason="soil_moisture_contract_mismatch",
                normalized_water_fraction=None,
                observed_at=None,
                calibration_signature=_signature(assignments, activation_id),
            )
        try:
            raw = float(state.state)
        except TypeError, ValueError:
            return SoilMoistureObservation(
                quality="incomplete",
                reason="soil_moisture_value_not_numeric",
                normalized_water_fraction=None,
                observed_at=None,
                calibration_signature=_signature(assignments, activation_id),
            )
        if not math.isfinite(raw) or not 0 <= raw <= 100:
            return SoilMoistureObservation(
                quality="implausible",
                reason="soil_moisture_outside_plausible_range",
                normalized_water_fraction=None,
                observed_at=None,
                calibration_signature=_signature(assignments, activation_id),
            )
        observed_at = (state.last_reported or state.last_updated).astimezone(UTC)
        if evaluated_at - observed_at > MAX_SOIL_MOISTURE_AGE:
            return SoilMoistureObservation(
                quality="stale",
                reason="soil_moisture_source_stale",
                normalized_water_fraction=None,
                observed_at=observed_at,
                calibration_signature=_signature(assignments, activation_id),
            )
        warnings: list[str] = []
        if raw < assignment.dry_percent:
            warnings.append("soil_moisture_below_dry_calibration")
        if raw > assignment.wet_percent:
            warnings.append("soil_moisture_above_wet_calibration")
        normalized = min(
            1.0,
            max(
                0.0,
                (raw - assignment.dry_percent) / (assignment.wet_percent - assignment.dry_percent),
            ),
        )
        readings.append(
            SoilMoistureReading(
                scope_id=assignment.scope_id,
                source_entity_id=assignment.entity_id,
                raw_percent=raw,
                normalized_water_fraction=normalized,
                observed_at=observed_at,
                weight=assignment.weight,
                warnings=tuple(warnings),
            )
        )
        all_warnings.extend(warnings)
    total_weight = sum(item.weight for item in readings)
    aggregate = (
        sum(item.normalized_water_fraction * item.weight for item in readings) / total_weight
    )
    return SoilMoistureObservation(
        quality="available",
        reason=None,
        normalized_water_fraction=aggregate,
        observed_at=min(item.observed_at for item in readings),
        calibration_signature=_signature(assignments, activation_id),
        readings=tuple(readings),
        warnings=tuple(dict.fromkeys(all_warnings)),
    )
