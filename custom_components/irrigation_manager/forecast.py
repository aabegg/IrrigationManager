"""Normalized Home Assistant rain forecasts and postponement decisions."""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from typing import cast

from homeassistant.components.weather.const import ATTR_WEATHER_PRECIPITATION_UNIT
from homeassistant.const import UnitOfPrecipitationDepth
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import DistanceConverter

from .const import WEEKDAYS
from .scheduler import resolve_local_wall_time

DEFAULT_MAXIMUM_MAKE_UP_DAYS = 2
MINIMUM_MAKE_UP_DAYS = 1
MAXIMUM_MAKE_UP_DAYS = 7
DEFAULT_MINIMUM_FORECAST_PRECIPITATION_MM = 3.0
DEFAULT_MINIMUM_FORECAST_PROBABILITY = 70.0


@dataclass(frozen=True, slots=True)
class ForecastPeriod:
    """One normalized forecast period in millimeters and percent."""

    starts_at: datetime
    ends_at: datetime
    precipitation_mm: float
    probability_percent: float


@dataclass(frozen=True, slots=True)
class ForecastSettings:
    """Thresholds controlling whether one due order may be postponed."""

    minimum_precipitation_mm: float
    minimum_probability_percent: float


@dataclass(frozen=True, slots=True)
class ForecastEvaluation:
    """Immutable evidence for one rain-forecast decision."""

    should_postpone: bool
    quality: str
    reason: str
    source_entity_id: str
    forecast_type: str
    evaluated_at: datetime
    next_opportunity_at: datetime
    considered_periods: tuple[ForecastPeriod, ...]
    qualified_periods: tuple[ForecastPeriod, ...]
    qualified_precipitation_mm: float


@dataclass(frozen=True, slots=True)
class NormalizedForecast:
    """Validated periods and stable quality evidence from one HA response."""

    periods: tuple[ForecastPeriod, ...]
    quality: str
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ForecastFetchResult:
    """Best supported normalized forecast returned by Home Assistant."""

    periods: tuple[ForecastPeriod, ...]
    quality: str
    warnings: tuple[str, ...]
    forecast_type: str | None


@dataclass(frozen=True, slots=True)
class MakeUpOpportunity:
    """One resolved local catch-up interval within a fixed deadline."""

    starts_at: datetime
    ends_at: datetime


def postponement_deadline(
    *, original_window_end: datetime, maximum_days: int, timezone: tzinfo
) -> datetime:
    """Add local calendar days without changing the original wall-clock end."""
    local_end = original_window_end.astimezone(timezone)
    return resolve_local_wall_time(
        local_end.date() + timedelta(days=maximum_days),
        local_end.time().replace(tzinfo=None),
        timezone,
    )


def next_make_up_opportunity(
    *,
    schedule: object,
    after: datetime,
    deadline: datetime,
    timezone: tzinfo,
) -> MakeUpOpportunity | None:
    """Return the first complete configured interval after a due window."""
    if not isinstance(schedule, list) or len(schedule) != len(WEEKDAYS):
        return None
    local_after = after.astimezone(timezone)
    local_deadline = deadline.astimezone(timezone)
    for offset in range((local_deadline.date() - local_after.date()).days + 1):
        day = local_after.date() + timedelta(days=offset)
        row = schedule[day.weekday()]
        if not isinstance(row, Mapping) or row.get("weekday") != WEEKDAYS[day.weekday()]:
            return None
        start_value = row.get("start")
        end_value = row.get("end")
        if start_value is None and end_value is None:
            continue
        if start_value is None or end_value is None:
            return None
        try:
            start_time = time.fromisoformat(str(start_value))
            end_time = time.fromisoformat(str(end_value))
        except ValueError:
            return None
        starts_at = resolve_local_wall_time(day, start_time, timezone)
        ends_at = resolve_local_wall_time(day, end_time, timezone)
        if ends_at <= starts_at:
            ends_at = resolve_local_wall_time(day + timedelta(days=1), end_time, timezone)
        if starts_at < after or ends_at > deadline:
            continue
        return MakeUpOpportunity(starts_at=starts_at, ends_at=ends_at)
    return None


async def async_fetch_forecast(
    hass: HomeAssistant,
    *,
    entity_id: str,
    supported_types: tuple[str, ...],
    timezone: tzinfo,
) -> ForecastFetchResult:
    """Fetch the best advertised native HA forecast with conservative fallback."""
    state = hass.states.get(entity_id)
    unit = None if state is None else state.attributes.get(ATTR_WEATHER_PRECIPITATION_UNIT)
    if not isinstance(unit, str):
        return ForecastFetchResult((), "invalid", ("forecast_precipitation_unit_invalid",), None)
    supported = set(supported_types)
    warnings: list[str] = []
    for forecast_type in ("hourly", "twice_daily", "daily"):
        if forecast_type not in supported:
            continue
        try:
            response = await hass.services.async_call(
                "weather",
                "get_forecasts",
                service_data={"type": forecast_type},
                target={"entity_id": entity_id},
                blocking=True,
                return_response=True,
            )
        except HomeAssistantError:
            warnings.append(f"forecast_action_failed:{forecast_type}")
            continue
        if not isinstance(response, Mapping):
            warnings.append(f"forecast_response_invalid:{forecast_type}")
            continue
        entity_response = response.get(entity_id)
        if not isinstance(entity_response, Mapping):
            warnings.append(f"forecast_response_invalid:{forecast_type}")
            continue
        raw = entity_response.get("forecast")
        if not isinstance(raw, list) or not all(isinstance(item, Mapping) for item in raw):
            warnings.append(f"forecast_response_invalid:{forecast_type}")
            continue
        normalized = normalize_forecast_periods(
            raw_forecast=cast(list[Mapping[str, object]], raw),
            forecast_type=forecast_type,
            precipitation_unit=unit,
            timezone=timezone,
        )
        combined_warnings = (*warnings, *normalized.warnings)
        if normalized.periods:
            return ForecastFetchResult(
                normalized.periods,
                normalized.quality,
                combined_warnings,
                forecast_type,
            )
        warnings.extend(normalized.warnings)
    if not supported.intersection({"hourly", "twice_daily", "daily"}):
        warnings.append("forecast_type_not_supported")
    return ForecastFetchResult((), "invalid", tuple(warnings), None)


def normalize_forecast_periods(
    *,
    raw_forecast: Sequence[Mapping[str, object]],
    forecast_type: str,
    precipitation_unit: str,
    timezone: tzinfo,
) -> NormalizedForecast:
    """Normalize complete HA weather periods without estimating missing fields."""
    periods: list[ForecastPeriod] = []
    warnings: list[str] = []
    for raw in raw_forecast:
        timestamp = raw.get("datetime")
        precipitation = raw.get("precipitation")
        probability = raw.get("precipitation_probability")
        if (
            isinstance(precipitation, bool)
            or not isinstance(precipitation, int | float)
            or isinstance(probability, bool)
            or not isinstance(probability, int | float)
        ):
            warnings.append("forecast_period_incomplete")
            continue
        precipitation_value = float(precipitation)
        probability_value = float(probability)
        if (
            not math.isfinite(precipitation_value)
            or precipitation_value < 0
            or not math.isfinite(probability_value)
            or not 0 <= probability_value <= 100
        ):
            warnings.append("forecast_period_unplausible")
            continue
        if not isinstance(timestamp, str):
            warnings.append("forecast_period_incomplete")
            continue
        try:
            starts_at = datetime.fromisoformat(timestamp)
        except ValueError:
            warnings.append("forecast_period_datetime_invalid")
            continue
        if starts_at.tzinfo is None:
            warnings.append("forecast_period_datetime_invalid")
            continue
        if forecast_type == "hourly":
            ends_at = starts_at + timedelta(hours=1)
        elif forecast_type == "twice_daily":
            ends_at = starts_at + timedelta(hours=12)
        elif forecast_type == "daily":
            local_start = starts_at.astimezone(timezone)
            if local_start.timetz().replace(tzinfo=None) != time.min:
                warnings.append("forecast_daily_period_incomplete")
                continue
            ends_at = datetime.combine(local_start.date() + timedelta(days=1), time.min, timezone)
        else:
            raise ValueError("Unsupported forecast type")
        try:
            precipitation_mm = DistanceConverter.convert(
                precipitation_value,
                precipitation_unit,
                UnitOfPrecipitationDepth.MILLIMETERS,
            )
        except ValueError:
            warnings.append("forecast_precipitation_unit_invalid")
            continue
        if not math.isfinite(precipitation_mm) or not 0 <= precipitation_mm <= 1_000:
            warnings.append("forecast_period_unplausible")
            continue
        periods.append(
            ForecastPeriod(
                starts_at=starts_at,
                ends_at=ends_at,
                precipitation_mm=precipitation_mm,
                probability_percent=probability_value,
            )
        )
    quality = "valid" if periods and not warnings else "partial" if periods else "invalid"
    return NormalizedForecast(tuple(periods), quality, tuple(warnings))


def evaluate_rain_forecast(
    *,
    periods: tuple[ForecastPeriod, ...],
    evaluated_at: datetime,
    next_opportunity_at: datetime,
    forecast_type: str,
    source_entity_id: str,
    settings: ForecastSettings,
) -> ForecastEvaluation:
    """Decide from complete forecast periods before the next opportunity."""
    considered = tuple(
        period
        for period in periods
        if period.starts_at >= evaluated_at and period.ends_at <= next_opportunity_at
    )
    qualified = tuple(
        period
        for period in considered
        if period.probability_percent >= settings.minimum_probability_percent
    )
    precipitation = sum(period.precipitation_mm for period in qualified)
    should_postpone = precipitation >= settings.minimum_precipitation_mm
    return ForecastEvaluation(
        should_postpone=should_postpone,
        quality="valid",
        reason=(
            "forecast_threshold_reached" if should_postpone else "forecast_threshold_not_reached"
        ),
        source_entity_id=source_entity_id,
        forecast_type=forecast_type,
        evaluated_at=evaluated_at,
        next_opportunity_at=next_opportunity_at,
        considered_periods=considered,
        qualified_periods=qualified,
        qualified_precipitation_mm=precipitation,
    )
