"""Persistent daily water balance and weather-based target resolution."""

import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum

from .soil_moisture import SoilMoistureObservation

MAX_SOIL_MOISTURE_CORRECTION_MM = 5.0


class WateringMode(StrEnum):
    """Decide whether a due date is optional or guarantees its seasonal baseline."""

    DEMAND = "demand"
    MINIMUM = "minimum"


@dataclass(frozen=True, slots=True)
class WeatherReading:
    """One normalized, usable weather-source reading."""

    source_entity_id: str
    value: float
    observed_at: datetime


@dataclass(frozen=True, slots=True)
class IrrigationContribution:
    """One completed execution that may contribute to a daily zone balance."""

    execution_id: str
    local_date: date
    target_type: str
    measurement_quality: str
    delivered_liters: float
    delivered_duration_seconds: float
    allocation_quality: str = "exact"
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProcessedIrrigationContribution:
    """One stable execution/day marker retained with the same 90-day horizon."""

    execution_id: str
    local_date: str
    outcome: str = "credited"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ProcessedIrrigationContribution:
        """Deserialize one persistent execution/day marker."""
        execution_id = data.get("execution_id")
        local_date = data.get("local_date")
        outcome = data.get("outcome", "credited")
        if not isinstance(execution_id, str) or not execution_id:
            raise ValueError("Stored processed execution ID is malformed")
        if not isinstance(local_date, str):
            raise ValueError("Stored processed execution date is malformed")
        date.fromisoformat(local_date)
        if outcome not in {"credited", "unreliable"}:
            raise ValueError("Stored processed execution outcome is malformed")
        return cls(execution_id=execution_id, local_date=local_date, outcome=str(outcome))

    def as_dict(self) -> dict[str, str]:
        """Serialize one persistent execution/day marker."""
        return {
            "execution_id": self.execution_id,
            "local_date": self.local_date,
            "outcome": self.outcome,
        }


@dataclass(frozen=True, slots=True)
class WeatherZoneSettings:
    """Physical zone values required to convert millimeters into a target."""

    watering_mode: WateringMode
    crop_factor: float
    effective_rain_factor: float
    demand_threshold_mm: float
    maximum_deficit_mm: float
    control_type: str
    effective_application_rate_mm_h: float | None = None
    irrigated_area_m2: float | None = None
    irrigation_efficiency: float | None = None

    def __post_init__(self) -> None:
        """Reject incomplete or physically unsafe conversion contracts."""
        if not math.isfinite(self.crop_factor) or not 0.1 <= self.crop_factor <= 2.0:
            raise ValueError("crop factor must be between 0.10 and 2.00")
        if not math.isfinite(self.effective_rain_factor) or not (
            0.0 <= self.effective_rain_factor <= 1.0
        ):
            raise ValueError("rain factor must be between 0 and 1")
        if not math.isfinite(self.demand_threshold_mm) or not (
            0.0 <= self.demand_threshold_mm <= 100.0
        ):
            raise ValueError("demand threshold is invalid")
        if not math.isfinite(self.maximum_deficit_mm) or not (
            1.0 <= self.maximum_deficit_mm <= 500.0
            and self.maximum_deficit_mm > self.demand_threshold_mm
        ):
            raise ValueError("maximum deficit must exceed the demand threshold")
        if self.control_type == "time":
            rate = self.effective_application_rate_mm_h
            if rate is None or not math.isfinite(rate) or not 0.1 <= rate <= 500.0:
                raise ValueError("application rate must be between 0.10 and 500 mm/h")
            return
        if self.control_type != "volume":
            raise ValueError("unsupported irrigation control type")
        area = self.irrigated_area_m2
        efficiency = self.irrigation_efficiency
        if area is None or not math.isfinite(area) or not 0.1 <= area <= 1_000_000.0:
            raise ValueError("irrigated area is invalid")
        if efficiency is None or not math.isfinite(efficiency) or not 0.1 <= efficiency <= 1.0:
            raise ValueError("irrigation efficiency is invalid")


@dataclass(frozen=True, slots=True)
class DailyWaterBalance:
    """Auditable contributions for one local calendar day."""

    local_date: str
    reference_et_source_entity_id: str
    reference_et_observed_at: str
    precipitation_source_entity_id: str
    precipitation_observed_at: str
    quality: str
    warnings: tuple[str, ...]
    opening_deficit_mm: float
    reference_evapotranspiration_mm: float
    plant_evapotranspiration_mm: float
    measured_precipitation_mm: float
    effective_precipitation_mm: float
    effective_irrigation_mm: float
    closing_deficit_mm: float
    soil_moisture_quality: str = "disabled"
    soil_moisture_reason: str | None = None
    soil_moisture_source_entity_ids: tuple[str, ...] = ()
    soil_moisture_observed_at: str | None = None
    soil_moisture_normalized_fraction: float | None = None
    soil_moisture_implied_deficit_mm: float | None = None
    soil_moisture_deadband_mm: float | None = None
    soil_moisture_correction_limit_mm: float | None = None
    soil_moisture_correction_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DailyWaterBalance:
        """Deserialize one strictly validated daily contribution record."""
        local_date = data.get("local_date")
        if not isinstance(local_date, str):
            raise ValueError("Stored water-balance date is malformed")
        date.fromisoformat(local_date)
        reference_source = data.get("reference_et_source_entity_id")
        reference_observed_at = data.get("reference_et_observed_at")
        precipitation_source = data.get("precipitation_source_entity_id")
        precipitation_observed_at = data.get("precipitation_observed_at")
        quality = data.get("quality")
        warnings = data.get("warnings", [])
        if not isinstance(reference_source, str) or not reference_source:
            raise ValueError("Stored reference ET source is malformed")
        if not isinstance(precipitation_source, str) or not precipitation_source:
            raise ValueError("Stored precipitation source is malformed")
        if not isinstance(reference_observed_at, str) or not isinstance(
            precipitation_observed_at, str
        ):
            raise ValueError("Stored weather observation time is malformed")
        datetime.fromisoformat(reference_observed_at)
        datetime.fromisoformat(precipitation_observed_at)
        if not isinstance(quality, str) or not quality:
            raise ValueError("Stored water-balance quality is malformed")
        if not isinstance(warnings, list) or not all(isinstance(item, str) for item in warnings):
            raise ValueError("Stored water-balance warnings are malformed")
        raw_source_ids = data.get("soil_moisture_source_entity_ids", [])
        if not isinstance(raw_source_ids, list) or not all(
            isinstance(item, str) for item in raw_source_ids
        ):
            raise ValueError("Stored soil-moisture sources are malformed")
        soil_observed_at = data.get("soil_moisture_observed_at")
        if soil_observed_at is not None:
            if not isinstance(soil_observed_at, str):
                raise ValueError("Stored soil-moisture observation time is malformed")
            datetime.fromisoformat(soil_observed_at)
        soil_quality = data.get("soil_moisture_quality", "disabled")
        soil_reason = data.get("soil_moisture_reason")
        if not isinstance(soil_quality, str) or (
            soil_reason is not None and not isinstance(soil_reason, str)
        ):
            raise ValueError("Stored soil-moisture decision is malformed")
        soil_correction_limit = _stored_optional_number(data, "soil_moisture_correction_limit_mm")
        if soil_correction_limit is not None and not (
            0.0 <= soil_correction_limit <= MAX_SOIL_MOISTURE_CORRECTION_MM
        ):
            raise ValueError("Stored soil-moisture correction limit is malformed")
        soil_correction = _stored_signed_number(data, "soil_moisture_correction_mm", default=0.0)
        if abs(soil_correction) > MAX_SOIL_MOISTURE_CORRECTION_MM:
            raise ValueError("Stored soil-moisture correction is malformed")
        return cls(
            local_date=local_date,
            reference_et_source_entity_id=reference_source,
            reference_et_observed_at=reference_observed_at,
            precipitation_source_entity_id=precipitation_source,
            precipitation_observed_at=precipitation_observed_at,
            quality=quality,
            warnings=tuple(warnings),
            opening_deficit_mm=_stored_number(data, "opening_deficit_mm"),
            reference_evapotranspiration_mm=_stored_number(data, "reference_evapotranspiration_mm"),
            plant_evapotranspiration_mm=_stored_number(data, "plant_evapotranspiration_mm"),
            measured_precipitation_mm=_stored_number(data, "measured_precipitation_mm"),
            effective_precipitation_mm=_stored_number(data, "effective_precipitation_mm"),
            effective_irrigation_mm=_stored_number(data, "effective_irrigation_mm"),
            closing_deficit_mm=_stored_number(data, "closing_deficit_mm"),
            soil_moisture_quality=soil_quality,
            soil_moisture_reason=soil_reason,
            soil_moisture_source_entity_ids=tuple(raw_source_ids),
            soil_moisture_observed_at=soil_observed_at,
            soil_moisture_normalized_fraction=_stored_optional_number(
                data, "soil_moisture_normalized_fraction"
            ),
            soil_moisture_implied_deficit_mm=_stored_optional_number(
                data, "soil_moisture_implied_deficit_mm"
            ),
            soil_moisture_deadband_mm=_stored_optional_number(data, "soil_moisture_deadband_mm"),
            soil_moisture_correction_limit_mm=soil_correction_limit,
            soil_moisture_correction_mm=soil_correction,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one daily contribution record."""
        return {
            "local_date": self.local_date,
            "reference_et_source_entity_id": self.reference_et_source_entity_id,
            "reference_et_observed_at": self.reference_et_observed_at,
            "precipitation_source_entity_id": self.precipitation_source_entity_id,
            "precipitation_observed_at": self.precipitation_observed_at,
            "quality": self.quality,
            "warnings": list(self.warnings),
            "opening_deficit_mm": self.opening_deficit_mm,
            "reference_evapotranspiration_mm": self.reference_evapotranspiration_mm,
            "plant_evapotranspiration_mm": self.plant_evapotranspiration_mm,
            "measured_precipitation_mm": self.measured_precipitation_mm,
            "effective_precipitation_mm": self.effective_precipitation_mm,
            "effective_irrigation_mm": self.effective_irrigation_mm,
            "closing_deficit_mm": self.closing_deficit_mm,
            "soil_moisture_quality": self.soil_moisture_quality,
            "soil_moisture_reason": self.soil_moisture_reason,
            "soil_moisture_source_entity_ids": list(self.soil_moisture_source_entity_ids),
            "soil_moisture_observed_at": self.soil_moisture_observed_at,
            "soil_moisture_normalized_fraction": self.soil_moisture_normalized_fraction,
            "soil_moisture_implied_deficit_mm": self.soil_moisture_implied_deficit_mm,
            "soil_moisture_deadband_mm": self.soil_moisture_deadband_mm,
            "soil_moisture_correction_limit_mm": self.soil_moisture_correction_limit_mm,
            "soil_moisture_correction_mm": self.soil_moisture_correction_mm,
        }


@dataclass(frozen=True, slots=True)
class ZoneWaterBalanceState:
    """Persistent progress for one weather-aware irrigation zone."""

    ready_from_date: str
    rain_source_entity_id: str
    rain_total_mm: float
    rain_observed_at: str
    days: tuple[DailyWaterBalance, ...]
    processed_executions: tuple[ProcessedIrrigationContribution, ...] = ()
    soil_moisture_calibration_signature: str | None = None
    soil_moisture_anchor_fraction: float | None = None
    soil_moisture_anchor_observed_at: str | None = None
    soil_moisture_last_correction_date: str | None = None

    @property
    def processed_execution_ids(self) -> tuple[str, ...]:
        """Expose execution IDs for diagnostics without discarding stored dates."""
        return tuple(item.execution_id for item in self.processed_executions)

    @property
    def unreliable_execution_ids(self) -> tuple[str, ...]:
        """Expose quarantined deliveries that were not credited as known zeroes."""
        return tuple(
            item.execution_id for item in self.processed_executions if item.outcome == "unreliable"
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ZoneWaterBalanceState:
        """Deserialize persistent balance progress without accepting partial state."""
        ready_from_date = data.get("ready_from_date")
        rain_source = data.get("rain_source_entity_id")
        rain_observed_at = data.get("rain_observed_at")
        raw_days = data.get("days")
        raw_ids = data.get("processed_execution_ids", [])
        if not isinstance(ready_from_date, str):
            raise ValueError("Stored ready-from date is malformed")
        date.fromisoformat(ready_from_date)
        if not isinstance(rain_source, str) or not rain_source:
            raise ValueError("Stored rain source is malformed")
        if not isinstance(rain_observed_at, str):
            raise ValueError("Stored rain observation time is malformed")
        datetime.fromisoformat(rain_observed_at)
        if (
            not isinstance(raw_days, list)
            or not raw_days
            or not all(isinstance(item, dict) for item in raw_days)
        ):
            raise ValueError("Stored water-balance days are malformed")
        if not isinstance(raw_ids, list) or not all(isinstance(item, dict) for item in raw_ids):
            raise ValueError("Stored processed execution IDs are malformed")
        calibration_signature = data.get("soil_moisture_calibration_signature")
        anchor_observed_at = data.get("soil_moisture_anchor_observed_at")
        last_correction_date = data.get("soil_moisture_last_correction_date")
        if calibration_signature is not None and not isinstance(calibration_signature, str):
            raise ValueError("Stored soil-moisture calibration is malformed")
        if anchor_observed_at is not None:
            if not isinstance(anchor_observed_at, str):
                raise ValueError("Stored soil-moisture anchor time is malformed")
            datetime.fromisoformat(anchor_observed_at)
        if last_correction_date is not None:
            if not isinstance(last_correction_date, str):
                raise ValueError("Stored soil-moisture correction date is malformed")
            date.fromisoformat(last_correction_date)
        anchor_fraction = _stored_optional_number(data, "soil_moisture_anchor_fraction")
        if anchor_fraction is not None and not 0.0 <= anchor_fraction <= 1.0:
            raise ValueError("Stored soil-moisture anchor is malformed")
        if (anchor_fraction is None) != (anchor_observed_at is None) or (
            anchor_fraction is not None and calibration_signature is None
        ):
            raise ValueError("Stored soil-moisture anchor is incomplete")
        return cls(
            ready_from_date=ready_from_date,
            rain_source_entity_id=rain_source,
            rain_total_mm=_stored_number(data, "rain_total_mm"),
            rain_observed_at=rain_observed_at,
            days=tuple(DailyWaterBalance.from_dict(item) for item in raw_days[-90:]),
            processed_executions=tuple(
                ProcessedIrrigationContribution.from_dict(item) for item in raw_ids
            ),
            soil_moisture_calibration_signature=calibration_signature,
            soil_moisture_anchor_fraction=anchor_fraction,
            soil_moisture_anchor_observed_at=anchor_observed_at,
            soil_moisture_last_correction_date=last_correction_date,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize persistent balance progress."""
        return {
            "ready_from_date": self.ready_from_date,
            "rain_source_entity_id": self.rain_source_entity_id,
            "rain_total_mm": self.rain_total_mm,
            "rain_observed_at": self.rain_observed_at,
            "days": [day.as_dict() for day in self.days[-90:]],
            "processed_execution_ids": [item.as_dict() for item in self.processed_executions],
            "soil_moisture_calibration_signature": self.soil_moisture_calibration_signature,
            "soil_moisture_anchor_fraction": self.soil_moisture_anchor_fraction,
            "soil_moisture_anchor_observed_at": self.soil_moisture_anchor_observed_at,
            "soil_moisture_last_correction_date": self.soil_moisture_last_correction_date,
        }


@dataclass(frozen=True, slots=True)
class WaterBalanceTargetResult:
    """One state transition and its automatic-target decision."""

    state: ZoneWaterBalanceState | None
    outcome: str
    final_target: float | None
    fallback_strategy: str
    quality: str
    warnings: tuple[str, ...] = ()
    reason: str | None = None
    deficit_target: float | None = None


def clear_soil_moisture_feedback_progress(
    state: ZoneWaterBalanceState,
) -> ZoneWaterBalanceState:
    """Remove feedback progress and its latest-day effect from the modeled balance."""
    latest = state.days[-1]
    modeled_closing_deficit = max(
        0.0,
        latest.closing_deficit_mm - latest.soil_moisture_correction_mm,
    )
    neutral_latest = replace(
        latest,
        warnings=tuple(
            warning for warning in latest.warnings if not warning.startswith("soil_moisture_")
        ),
        closing_deficit_mm=modeled_closing_deficit,
        soil_moisture_quality="disabled",
        soil_moisture_reason=None,
        soil_moisture_source_entity_ids=(),
        soil_moisture_observed_at=None,
        soil_moisture_normalized_fraction=None,
        soil_moisture_implied_deficit_mm=None,
        soil_moisture_deadband_mm=None,
        soil_moisture_correction_limit_mm=None,
        soil_moisture_correction_mm=0.0,
    )
    return replace(
        state,
        days=(*state.days[:-1], neutral_latest),
        soil_moisture_calibration_signature=None,
        soil_moisture_anchor_fraction=None,
        soil_moisture_anchor_observed_at=None,
        soil_moisture_last_correction_date=None,
    )


def _stored_number(data: dict[str, object], key: str) -> float:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Stored {key} is not numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"Stored {key} is invalid")
    return result


def _stored_optional_number(data: dict[str, object], key: str) -> float | None:
    value = data.get(key)
    if value is None:
        return None
    return _stored_number(data, key)


def _stored_signed_number(
    data: dict[str, object], key: str, *, default: float | None = None
) -> float:
    value = data.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Stored {key} is not numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Stored {key} is invalid")
    return result


def _target_depth_mm(settings: WeatherZoneSettings, target: float) -> float:
    if settings.control_type == "time":
        rate = settings.effective_application_rate_mm_h
        if rate is None or rate <= 0:
            raise ValueError("Time control requires an effective application rate")
        return target / 3600 * rate
    if settings.control_type == "volume":
        area = settings.irrigated_area_m2
        efficiency = settings.irrigation_efficiency
        if area is None or area <= 0 or efficiency is None or efficiency <= 0:
            raise ValueError("Volume control requires area and irrigation efficiency")
        return target * efficiency / area
    raise ValueError("Unsupported irrigation control type")


def _depth_target(settings: WeatherZoneSettings, depth_mm: float) -> float:
    if settings.control_type == "time":
        rate = settings.effective_application_rate_mm_h
        if rate is None or rate <= 0:
            raise ValueError("Time control requires an effective application rate")
        return depth_mm / rate * 3600
    if settings.control_type == "volume":
        area = settings.irrigated_area_m2
        efficiency = settings.irrigation_efficiency
        if area is None or area <= 0 or efficiency is None or efficiency <= 0:
            raise ValueError("Volume control requires area and irrigation efficiency")
        return depth_mm * area / efficiency
    raise ValueError("Unsupported irrigation control type")


def _irrigation_depth_mm(
    settings: WeatherZoneSettings, contribution: IrrigationContribution
) -> float:
    if settings.control_type == "time":
        rate = settings.effective_application_rate_mm_h
        if rate is None or rate <= 0:
            raise ValueError("Time control requires an effective application rate")
        return contribution.delivered_duration_seconds / 3600 * rate
    area = settings.irrigated_area_m2
    efficiency = settings.irrigation_efficiency
    if area is None or area <= 0 or efficiency is None or efficiency <= 0:
        raise ValueError("Volume control requires area and irrigation efficiency")
    return contribution.delivered_liters * efficiency / area


def _contribution_marker(
    contribution: IrrigationContribution,
) -> ProcessedIrrigationContribution:
    return ProcessedIrrigationContribution(
        execution_id=contribution.execution_id,
        local_date=contribution.local_date.isoformat(),
    )


def _contribution_warning(
    settings: WeatherZoneSettings, contribution: IrrigationContribution
) -> str | None:
    expected_type = "duration" if settings.control_type == "time" else "volume"
    if contribution.allocation_quality != "exact":
        return "irrigation_timing_unavailable"
    if contribution.target_type != expected_type:
        return "irrigation_control_type_changed"
    if settings.control_type == "volume" and contribution.measurement_quality != "measured":
        return "irrigation_delivery_unavailable"
    required_value = (
        contribution.delivered_duration_seconds
        if settings.control_type == "time"
        else contribution.delivered_liters
    )
    if not math.isfinite(required_value) or required_value < 0:
        return "irrigation_delivery_invalid"
    return None


def _retained_processed(
    processed: tuple[ProcessedIrrigationContribution, ...], current_date: date
) -> list[ProcessedIrrigationContribution]:
    earliest = current_date - timedelta(days=89)
    return [item for item in processed if date.fromisoformat(item.local_date) >= earliest]


def _recover_historical_irrigation(
    state: ZoneWaterBalanceState | None,
    settings: WeatherZoneSettings,
    contributions: tuple[IrrigationContribution, ...],
    *,
    current_date: date,
) -> ZoneWaterBalanceState | None:
    """Apply terminal executions that were persisted before their planner acknowledgement."""
    if state is None:
        return None
    days = list(state.days)
    day_indexes = {date.fromisoformat(day.local_date): index for index, day in enumerate(days)}
    processed = _retained_processed(state.processed_executions, current_date)
    seen = {(item.execution_id, item.local_date) for item in processed}
    first_changed: int | None = None
    for contribution in contributions:
        index = day_indexes.get(contribution.local_date)
        if (
            contribution.local_date >= current_date
            or (contribution.execution_id, contribution.local_date.isoformat()) in seen
            or index is None
            or _contribution_warning(settings, contribution) is not None
        ):
            continue
        day = days[index]
        days[index] = replace(
            day,
            effective_irrigation_mm=(
                day.effective_irrigation_mm + _irrigation_depth_mm(settings, contribution)
            ),
            warnings=tuple(
                dict.fromkeys((*day.warnings, *contribution.warnings, "late_irrigation_recovered"))
            ),
        )
        marker = _contribution_marker(contribution)
        seen.add((marker.execution_id, marker.local_date))
        processed.append(marker)
        first_changed = index if first_changed is None else min(first_changed, index)
    if first_changed is None:
        return state
    for index in range(first_changed, len(days)):
        day = days[index]
        opening = day.opening_deficit_mm if index == 0 else days[index - 1].closing_deficit_mm
        closing = min(
            settings.maximum_deficit_mm,
            max(
                0.0,
                opening
                + day.plant_evapotranspiration_mm
                - day.effective_precipitation_mm
                - day.effective_irrigation_mm,
            ),
        )
        days[index] = replace(
            day,
            opening_deficit_mm=opening,
            closing_deficit_mm=closing,
        )
    return replace(
        state,
        days=tuple(days),
        processed_executions=tuple(processed),
    )


@dataclass(frozen=True, slots=True)
class _SoilMoistureTransition:
    day: DailyWaterBalance
    calibration_signature: str | None
    anchor_fraction: float | None
    anchor_observed_at: str | None
    last_correction_date: str | None
    warnings: tuple[str, ...]


def _apply_soil_moisture_feedback(
    *,
    state: ZoneWaterBalanceState,
    day: DailyWaterBalance,
    settings: WeatherZoneSettings,
    current_date: date,
    enabled: bool,
    observation: SoilMoistureObservation | None,
) -> _SoilMoistureTransition:
    """Apply at most one confirmed and bounded correction for one local day."""
    if not enabled:
        return _SoilMoistureTransition(day, None, None, None, None, ())

    previous_day = state.days[-1]
    corrected_today = (
        state.soil_moisture_last_correction_date == current_date.isoformat()
        and previous_day.local_date == current_date.isoformat()
    )
    deadband = max(1.0, settings.maximum_deficit_mm * 0.05)
    correction_limit = min(MAX_SOIL_MOISTURE_CORRECTION_MM, settings.maximum_deficit_mm * 0.25)

    def preserved_correction() -> float:
        if not corrected_today:
            return 0.0
        return max(
            -correction_limit,
            min(correction_limit, previous_day.soil_moisture_correction_mm),
        )

    if observation is None or observation.quality != "available":
        reason = (
            "soil_moisture_observation_unavailable"
            if observation is None
            else observation.reason or f"soil_moisture_{observation.quality}"
        )
        preserved = preserved_correction()
        return _SoilMoistureTransition(
            replace(
                day,
                warnings=tuple(dict.fromkeys((*day.warnings, reason))),
                closing_deficit_mm=min(
                    settings.maximum_deficit_mm,
                    max(0.0, day.closing_deficit_mm + preserved),
                ),
                soil_moisture_quality=(
                    "unavailable" if observation is None else observation.quality
                ),
                soil_moisture_reason=reason,
                soil_moisture_deadband_mm=deadband if corrected_today else None,
                soil_moisture_correction_limit_mm=(correction_limit if corrected_today else None),
                soil_moisture_correction_mm=preserved,
            ),
            None if observation is None else observation.calibration_signature,
            None,
            None,
            state.soil_moisture_last_correction_date,
            (reason,),
        )

    fraction = observation.normalized_water_fraction
    observed_at = observation.observed_at
    signature = observation.calibration_signature
    if (
        fraction is None
        or observed_at is None
        or signature is None
        or not math.isfinite(fraction)
        or not 0 <= fraction <= 1
    ):
        return _SoilMoistureTransition(
            replace(
                day,
                soil_moisture_quality="incomplete",
                soil_moisture_reason="soil_moisture_observation_incomplete",
            ),
            state.soil_moisture_calibration_signature,
            state.soil_moisture_anchor_fraction,
            state.soil_moisture_anchor_observed_at,
            state.soil_moisture_last_correction_date,
            ("soil_moisture_observation_incomplete",),
        )

    implied_deficit = (1.0 - fraction) * settings.maximum_deficit_mm

    def evidence_day(*, quality: str, reason: str) -> DailyWaterBalance:
        return replace(
            day,
            warnings=tuple(dict.fromkeys((*day.warnings, *observation.warnings, reason))),
            soil_moisture_quality=quality,
            soil_moisture_reason=reason,
            soil_moisture_source_entity_ids=observation.source_entity_ids,
            soil_moisture_observed_at=observed_at.isoformat(),
            soil_moisture_normalized_fraction=fraction,
            soil_moisture_implied_deficit_mm=implied_deficit,
        )

    def observe_only(
        reason: str, *, preserve_applied_correction: bool = False
    ) -> _SoilMoistureTransition:
        warnings = tuple(dict.fromkeys((*observation.warnings, reason)))
        preserved = preserved_correction() if preserve_applied_correction else 0.0
        return _SoilMoistureTransition(
            replace(
                evidence_day(quality="observing", reason=reason),
                closing_deficit_mm=min(
                    settings.maximum_deficit_mm,
                    max(0.0, day.closing_deficit_mm + preserved),
                ),
                soil_moisture_deadband_mm=deadband if corrected_today else None,
                soil_moisture_correction_limit_mm=(correction_limit if corrected_today else None),
                soil_moisture_correction_mm=preserved,
            ),
            signature,
            fraction,
            observed_at.isoformat(),
            state.soil_moisture_last_correction_date,
            warnings,
        )

    if state.soil_moisture_calibration_signature != signature:
        return observe_only("soil_moisture_observing")
    if (
        state.soil_moisture_anchor_fraction is None
        or state.soil_moisture_anchor_observed_at is None
    ):
        return observe_only("soil_moisture_observing", preserve_applied_correction=corrected_today)
    if corrected_today:
        preserved = preserved_correction()
        reason = "soil_moisture_daily_limit_reached"
        return _SoilMoistureTransition(
            replace(
                evidence_day(quality="available", reason=reason),
                closing_deficit_mm=min(
                    settings.maximum_deficit_mm,
                    max(0.0, day.closing_deficit_mm + preserved),
                ),
                soil_moisture_deadband_mm=deadband,
                soil_moisture_correction_limit_mm=correction_limit,
                soil_moisture_correction_mm=preserved,
            ),
            signature,
            state.soil_moisture_anchor_fraction,
            state.soil_moisture_anchor_observed_at,
            state.soil_moisture_last_correction_date,
            tuple(dict.fromkeys((*observation.warnings, reason))),
        )
    try:
        anchor_at = datetime.fromisoformat(state.soil_moisture_anchor_observed_at)
    except ValueError:
        return observe_only("soil_moisture_observing")
    elapsed = (observed_at - anchor_at).total_seconds()
    if elapsed < 1_800:
        return _SoilMoistureTransition(
            evidence_day(
                quality="observing",
                reason="soil_moisture_confirmation_pending",
            ),
            signature,
            state.soil_moisture_anchor_fraction,
            state.soil_moisture_anchor_observed_at,
            state.soil_moisture_last_correction_date,
            tuple(dict.fromkeys((*observation.warnings, "soil_moisture_confirmation_pending"))),
        )
    if elapsed > 21_600:
        return observe_only("soil_moisture_observing")
    if abs(fraction - state.soil_moisture_anchor_fraction) > 0.20:
        return observe_only("soil_moisture_jump_detected")

    difference = implied_deficit - day.closing_deficit_mm
    correction = (
        0.0
        if abs(difference) <= deadband
        else max(-correction_limit, min(correction_limit, difference))
    )
    corrected_deficit = min(
        settings.maximum_deficit_mm,
        max(0.0, day.closing_deficit_mm + correction),
    )
    reason = (
        "soil_moisture_within_deadband" if correction == 0 else "soil_moisture_correction_applied"
    )
    warnings = tuple(dict.fromkeys((*observation.warnings,)))
    return _SoilMoistureTransition(
        replace(
            evidence_day(quality="available", reason=reason),
            closing_deficit_mm=corrected_deficit,
            soil_moisture_deadband_mm=deadband,
            soil_moisture_correction_limit_mm=correction_limit,
            soil_moisture_correction_mm=correction,
        ),
        signature,
        fraction,
        observed_at.isoformat(),
        current_date.isoformat() if correction != 0 else state.soil_moisture_last_correction_date,
        warnings,
    )


def update_water_balance(
    *,
    state: ZoneWaterBalanceState | None,
    settings: WeatherZoneSettings,
    current_date: date,
    target_date: date,
    seasonal_base_target: float,
    reference_et: WeatherReading | None,
    precipitation_total: WeatherReading | None,
    irrigation_contributions: tuple[IrrigationContribution, ...] = (),
    soil_moisture_feedback_enabled: bool = False,
    soil_moisture_observation: SoilMoistureObservation | None = None,
) -> WaterBalanceTargetResult:
    """Advance one zone balance and resolve a due automatic target.

    The transition is deliberately conservative: unavailable, stale, reordered, or
    discontinuous observations preserve the established seasonal target.
    """
    state = _recover_historical_irrigation(
        state,
        settings,
        irrigation_contributions,
        current_date=current_date,
    )

    def fallback(strategy: str) -> WaterBalanceTargetResult:
        return WaterBalanceTargetResult(
            state=state,
            outcome="execute",
            final_target=seasonal_base_target,
            fallback_strategy=strategy,
            quality="fallback",
            warnings=(strategy,),
        )

    if reference_et is None or precipitation_total is None:
        return fallback("weather_sources_unavailable")
    if not all(
        math.isfinite(value) and value >= 0
        for value in (seasonal_base_target, reference_et.value, precipitation_total.value)
    ):
        return fallback("weather_observations_invalid")
    if (
        reference_et.observed_at.date() != current_date
        or precipitation_total.observed_at.date() != current_date
    ):
        return fallback("weather_observations_not_current")

    def new_contributions(
        processed: tuple[ProcessedIrrigationContribution, ...],
    ) -> tuple[tuple[IrrigationContribution, ...], tuple[ProcessedIrrigationContribution, ...]]:
        retained = _retained_processed(processed, current_date)
        seen = {(item.execution_id, item.local_date) for item in retained}
        additions: list[IrrigationContribution] = []
        for contribution in irrigation_contributions:
            marker = _contribution_marker(contribution)
            key = (marker.execution_id, marker.local_date)
            if (
                contribution.local_date != current_date
                or key in seen
                or _contribution_warning(settings, contribution) is not None
            ):
                continue
            additions.append(contribution)
            retained.append(marker)
            seen.add(key)
        return tuple(additions), tuple(retained)

    def make_day(
        *,
        opening: float,
        measured_rain: float,
        effective_irrigation: float,
        irrigation_warnings: tuple[str, ...] = (),
    ) -> DailyWaterBalance:
        plant_et = reference_et.value * settings.crop_factor
        effective_rain = measured_rain * settings.effective_rain_factor
        closing = min(
            settings.maximum_deficit_mm,
            max(0.0, opening + plant_et - effective_rain - effective_irrigation),
        )
        return DailyWaterBalance(
            local_date=current_date.isoformat(),
            reference_et_source_entity_id=reference_et.source_entity_id,
            reference_et_observed_at=reference_et.observed_at.isoformat(),
            precipitation_source_entity_id=precipitation_total.source_entity_id,
            precipitation_observed_at=precipitation_total.observed_at.isoformat(),
            quality="available",
            warnings=tuple(dict.fromkeys(irrigation_warnings)),
            opening_deficit_mm=opening,
            reference_evapotranspiration_mm=reference_et.value,
            plant_evapotranspiration_mm=plant_et,
            measured_precipitation_mm=measured_rain,
            effective_precipitation_mm=effective_rain,
            effective_irrigation_mm=effective_irrigation,
            closing_deficit_mm=closing,
        )

    def reinitialize(
        warning: str,
        *,
        unreliable: ProcessedIrrigationContribution | None = None,
    ) -> WaterBalanceTargetResult:
        existing_days = state.days if state is not None else ()
        processed = state.processed_executions if state is not None else ()
        previous_same_day = (
            existing_days[-1]
            if existing_days and existing_days[-1].local_date == current_date.isoformat()
            else None
        )
        additions, processed_ids = new_contributions(processed)
        if unreliable is not None and all(
            (item.execution_id, item.local_date) != (unreliable.execution_id, unreliable.local_date)
            for item in processed_ids
        ):
            processed_ids = (*processed_ids, replace(unreliable, outcome="unreliable"))
        effective_irrigation = (
            previous_same_day.effective_irrigation_mm if previous_same_day is not None else 0.0
        ) + sum(_irrigation_depth_mm(settings, item) for item in additions)
        day = make_day(
            opening=_target_depth_mm(settings, seasonal_base_target),
            measured_rain=0.0,
            effective_irrigation=effective_irrigation,
            irrigation_warnings=tuple(warning for item in additions for warning in item.warnings),
        )
        day = replace(
            day,
            quality="fallback",
            warnings=tuple(dict.fromkeys((*day.warnings, warning))),
        )
        days = (
            (*existing_days[:-1], day) if previous_same_day is not None else (*existing_days, day)
        )[-90:]
        initialized = ZoneWaterBalanceState(
            ready_from_date=(current_date + timedelta(days=1)).isoformat(),
            rain_source_entity_id=precipitation_total.source_entity_id,
            rain_total_mm=precipitation_total.value,
            rain_observed_at=precipitation_total.observed_at.isoformat(),
            days=days,
            processed_executions=processed_ids,
        )
        return WaterBalanceTargetResult(
            state=initialized,
            outcome="execute",
            final_target=seasonal_base_target,
            fallback_strategy="water_balance_reinitializing",
            quality="fallback",
            warnings=(warning,),
        )

    if state is None:
        result = reinitialize("water_balance_initializing")
        return WaterBalanceTargetResult(
            state=result.state,
            outcome=result.outcome,
            final_target=result.final_target,
            fallback_strategy=(
                "water_balance_initializing"
                if target_date == current_date
                else "future_date_without_forecast"
            ),
            quality=result.quality,
            warnings=(),
        )

    processed_keys = {(item.execution_id, item.local_date) for item in state.processed_executions}
    unsafe_warning: str | None = None
    unsafe_marker: ProcessedIrrigationContribution | None = None
    for contribution in irrigation_contributions:
        marker = _contribution_marker(contribution)
        if (
            contribution.local_date <= current_date
            and (marker.execution_id, marker.local_date) not in processed_keys
        ):
            unsafe_warning = _contribution_warning(settings, contribution)
            if unsafe_warning is not None:
                unsafe_marker = marker
                break
    if unsafe_warning is not None:
        return reinitialize(unsafe_warning, unreliable=unsafe_marker)

    previous = state.days[-1]
    previous_date = date.fromisoformat(previous.local_date)
    if reference_et.source_entity_id != previous.reference_et_source_entity_id:
        return reinitialize("reference_et_source_changed")
    if precipitation_total.source_entity_id != state.rain_source_entity_id:
        return reinitialize("precipitation_source_changed")
    if current_date < previous_date:
        return reinitialize("water_balance_clock_regression")
    if current_date > previous_date + timedelta(days=1):
        return reinitialize("water_balance_observation_gap")
    if current_date == previous_date and (
        precipitation_total.observed_at < datetime.fromisoformat(state.rain_observed_at)
        or reference_et.observed_at < datetime.fromisoformat(previous.reference_et_observed_at)
    ):
        return fallback("weather_observations_out_of_order")

    additions, processed_ids = new_contributions(state.processed_executions)
    added_irrigation = sum(_irrigation_depth_mm(settings, item) for item in additions)
    warnings = tuple(dict.fromkeys(warning for item in additions for warning in item.warnings))
    if current_date == previous_date:
        rain_delta = precipitation_total.value - state.rain_total_mm
        if rain_delta < 0:
            return reinitialize("precipitation_counter_reset")
        measured_rain = previous.measured_precipitation_mm + rain_delta
        effective_irrigation = previous.effective_irrigation_mm + added_irrigation
        day = make_day(
            opening=previous.opening_deficit_mm,
            measured_rain=measured_rain,
            effective_irrigation=effective_irrigation,
            irrigation_warnings=warnings,
        )
        days = (*state.days[:-1], day)
    else:
        rain_delta = precipitation_total.value - state.rain_total_mm
        if rain_delta < 0:
            rain_delta = precipitation_total.value
            warnings = tuple(dict.fromkeys((*warnings, "precipitation_counter_reset")))
        day = make_day(
            opening=previous.closing_deficit_mm,
            measured_rain=rain_delta,
            effective_irrigation=added_irrigation,
            irrigation_warnings=warnings,
        )
        if warnings:
            day = replace(day, warnings=warnings)
        days = (*state.days, day)[-90:]

    soil_transition = _apply_soil_moisture_feedback(
        state=state,
        day=day,
        settings=settings,
        current_date=current_date,
        enabled=soil_moisture_feedback_enabled,
        observation=soil_moisture_observation,
    )
    day = soil_transition.day
    days = (*days[:-1], day)
    warnings = tuple(dict.fromkeys((*warnings, *soil_transition.warnings)))
    updated = ZoneWaterBalanceState(
        ready_from_date=state.ready_from_date,
        rain_source_entity_id=state.rain_source_entity_id,
        rain_total_mm=precipitation_total.value,
        rain_observed_at=precipitation_total.observed_at.isoformat(),
        days=days,
        processed_executions=processed_ids,
        soil_moisture_calibration_signature=soil_transition.calibration_signature,
        soil_moisture_anchor_fraction=soil_transition.anchor_fraction,
        soil_moisture_anchor_observed_at=soil_transition.anchor_observed_at,
        soil_moisture_last_correction_date=soil_transition.last_correction_date,
    )
    if target_date != current_date:
        return WaterBalanceTargetResult(
            state=updated,
            outcome="execute",
            final_target=seasonal_base_target,
            fallback_strategy="future_date_without_forecast",
            quality="fallback",
            warnings=warnings,
        )
    if current_date < date.fromisoformat(updated.ready_from_date):
        return WaterBalanceTargetResult(
            state=updated,
            outcome="execute",
            final_target=seasonal_base_target,
            fallback_strategy="water_balance_initializing",
            quality="fallback",
            warnings=warnings,
        )
    if (
        settings.watering_mode is WateringMode.DEMAND
        and day.closing_deficit_mm < settings.demand_threshold_mm
    ):
        return WaterBalanceTargetResult(
            state=updated,
            outcome="skip",
            final_target=None,
            fallback_strategy="none",
            quality="valid",
            warnings=warnings,
            reason="water_deficit_below_threshold",
            deficit_target=0.0,
        )
    deficit_target = _depth_target(settings, day.closing_deficit_mm)
    resolved_target = deficit_target
    if settings.watering_mode is WateringMode.MINIMUM:
        resolved_target = max(seasonal_base_target, resolved_target)
    return WaterBalanceTargetResult(
        state=updated,
        outcome="execute",
        final_target=resolved_target,
        fallback_strategy="none",
        quality="valid",
        warnings=warnings,
        deficit_target=deficit_target,
    )
