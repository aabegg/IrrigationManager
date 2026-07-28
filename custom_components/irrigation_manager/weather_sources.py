"""Weather-source roles and normalized observation contracts."""

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

from homeassistant.components.weather.const import WeatherEntityFeature
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfIrradiance,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    SpeedConverter,
    TemperatureConverter,
)


class WeatherSourceRole(StrEnum):
    """One explicit semantic role assigned to a Home Assistant entity."""

    PRECIPITATION_TOTAL = "precipitation_total"
    PRECIPITATION_RATE = "precipitation_rate"
    REFERENCE_EVAPOTRANSPIRATION = "reference_evapotranspiration"
    AIR_TEMPERATURE = "air_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"
    DEW_POINT = "dew_point"
    WIND_SPEED = "wind_speed"
    SOLAR_IRRADIANCE = "solar_irradiance"
    FORECAST = "forecast"


WEATHER_SOURCE_ROLES = tuple(WeatherSourceRole)


class WeatherSourceQuality(StrEnum):
    """Validity of one normalized weather-source observation."""

    NOT_CONFIGURED = "not_configured"
    AVAILABLE = "available"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    IMPLAUSIBLE = "implausible"
    INCOMPLETE = "incomplete"


@dataclass(frozen=True, slots=True)
class WeatherSourceObservation:
    """One normalized reading without any effect on irrigation planning."""

    source_entity_id: str | None
    quality: str
    reason: str | None
    value: float | None
    unit: str | None
    observed_at: str | None
    age_seconds: float | None
    supported_forecast_types: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return one JSON-compatible diagnostics record."""
        result = asdict(self)
        result["supported_forecast_types"] = list(self.supported_forecast_types)
        return result


@dataclass(frozen=True, slots=True)
class _SourceContract:
    """Normalization and validation rules for one semantic role."""

    canonical_unit: str | None
    max_age: timedelta
    minimum: float | None = None
    maximum: float | None = None
    sensor_device_class: str | None = None
    sensor_state_classes: frozenset[str] | None = None
    weather_attribute: str | None = None
    weather_unit_attribute: str | None = None


_CONTRACTS: Final = {
    WeatherSourceRole.PRECIPITATION_TOTAL: _SourceContract(
        UnitOfPrecipitationDepth.MILLIMETERS,
        timedelta(hours=6),
        minimum=0,
        sensor_device_class="precipitation",
        sensor_state_classes=frozenset({"total", "total_increasing"}),
    ),
    WeatherSourceRole.PRECIPITATION_RATE: _SourceContract(
        UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        timedelta(minutes=30),
        minimum=0,
        maximum=1000,
        sensor_device_class="precipitation_intensity",
    ),
    WeatherSourceRole.REFERENCE_EVAPOTRANSPIRATION: _SourceContract(
        "mm/d",
        timedelta(hours=36),
        minimum=0,
        maximum=30,
        sensor_state_classes=frozenset({"total", "total_increasing"}),
    ),
    WeatherSourceRole.AIR_TEMPERATURE: _SourceContract(
        UnitOfTemperature.CELSIUS,
        timedelta(hours=2),
        minimum=-90,
        maximum=60,
        sensor_device_class="temperature",
        weather_attribute="temperature",
        weather_unit_attribute="temperature_unit",
    ),
    WeatherSourceRole.RELATIVE_HUMIDITY: _SourceContract(
        "%",
        timedelta(hours=2),
        minimum=0,
        maximum=100,
        sensor_device_class="humidity",
        weather_attribute="humidity",
    ),
    WeatherSourceRole.DEW_POINT: _SourceContract(
        UnitOfTemperature.CELSIUS,
        timedelta(hours=2),
        minimum=-100,
        maximum=60,
        sensor_device_class="temperature",
        weather_attribute="dew_point",
        weather_unit_attribute="temperature_unit",
    ),
    WeatherSourceRole.WIND_SPEED: _SourceContract(
        UnitOfSpeed.METERS_PER_SECOND,
        timedelta(hours=2),
        minimum=0,
        maximum=120,
        sensor_device_class="wind_speed",
        weather_attribute="wind_speed",
        weather_unit_attribute="wind_speed_unit",
    ),
    WeatherSourceRole.SOLAR_IRRADIANCE: _SourceContract(
        UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        timedelta(hours=2),
        minimum=0,
        maximum=1600,
        sensor_device_class="irradiance",
    ),
    WeatherSourceRole.FORECAST: _SourceContract(None, timedelta(hours=6)),
}

_FORECAST_FEATURES: Final = (
    (WeatherEntityFeature.FORECAST_DAILY, "daily"),
    (WeatherEntityFeature.FORECAST_HOURLY, "hourly"),
    (WeatherEntityFeature.FORECAST_TWICE_DAILY, "twice_daily"),
)


def _observation(
    *,
    entity_id: str | None,
    quality: WeatherSourceQuality,
    reason: str | None,
    value: float | None = None,
    unit: str | None = None,
    state: State | None = None,
    now: datetime,
    supported_forecast_types: tuple[str, ...] = (),
) -> WeatherSourceObservation:
    observed = None if state is None else state.last_reported or state.last_updated
    age = None if observed is None else max(0.0, (now - observed.astimezone(UTC)).total_seconds())
    return WeatherSourceObservation(
        source_entity_id=entity_id,
        quality=quality,
        reason=reason,
        value=value,
        unit=unit,
        observed_at=None if observed is None else observed.isoformat(),
        age_seconds=age,
        supported_forecast_types=supported_forecast_types,
    )


def _convert_value(role: WeatherSourceRole, value: float, unit: object) -> float:
    """Convert one validated numeric source value into its canonical unit."""
    if not isinstance(unit, str):
        raise HomeAssistantError("Source unit is missing")
    if role is WeatherSourceRole.PRECIPITATION_TOTAL:
        return DistanceConverter.convert(
            value,
            unit,
            UnitOfPrecipitationDepth.MILLIMETERS,
        )
    if role is WeatherSourceRole.REFERENCE_EVAPOTRANSPIRATION:
        distance_unit = {
            "mm/d": UnitOfPrecipitationDepth.MILLIMETERS,
            "mm/day": UnitOfPrecipitationDepth.MILLIMETERS,
            "mm/24h": UnitOfPrecipitationDepth.MILLIMETERS,
            "in/d": UnitOfPrecipitationDepth.INCHES,
            "in/day": UnitOfPrecipitationDepth.INCHES,
            "in/24h": UnitOfPrecipitationDepth.INCHES,
        }.get(unit.strip().lower(), unit)
        return DistanceConverter.convert(
            value,
            distance_unit,
            UnitOfPrecipitationDepth.MILLIMETERS,
        )
    if role is WeatherSourceRole.PRECIPITATION_RATE:
        return SpeedConverter.convert(
            value,
            unit,
            UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        )
    if role in {WeatherSourceRole.AIR_TEMPERATURE, WeatherSourceRole.DEW_POINT}:
        return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
    if role is WeatherSourceRole.WIND_SPEED:
        return SpeedConverter.convert(value, unit, UnitOfSpeed.METERS_PER_SECOND)
    if role is WeatherSourceRole.SOLAR_IRRADIANCE:
        if unit == UnitOfIrradiance.WATTS_PER_SQUARE_METER:
            return value
        if unit == UnitOfIrradiance.BTUS_PER_HOUR_SQUARE_FOOT:
            return value * 3.15459075
        raise HomeAssistantError("Source unit is not supported")
    if role is WeatherSourceRole.RELATIVE_HUMIDITY and unit == "%":
        return value
    raise HomeAssistantError("Source unit is not supported")


def _forecast_observation(
    entity_id: str,
    state: State,
    *,
    now: datetime,
) -> WeatherSourceObservation:
    if not entity_id.startswith("weather."):
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.INCOMPLETE,
            reason="source_contract_mismatch",
            state=state,
            now=now,
        )
    supported = state.attributes.get("supported_features")
    feature_value = (
        supported if isinstance(supported, int) and not isinstance(supported, bool) else 0
    )
    forecast_types = tuple(name for feature, name in _FORECAST_FEATURES if feature_value & feature)
    if not forecast_types:
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.INCOMPLETE,
            reason="forecast_not_supported",
            state=state,
            now=now,
        )
    return _available_or_stale(
        entity_id,
        state,
        _CONTRACTS[WeatherSourceRole.FORECAST],
        now=now,
        value=None,
        supported_forecast_types=forecast_types,
    )


def _available_or_stale(
    entity_id: str,
    state: State,
    contract: _SourceContract,
    *,
    now: datetime,
    value: float | None,
    supported_forecast_types: tuple[str, ...] = (),
) -> WeatherSourceObservation:
    observed = state.last_reported or state.last_updated
    age = max(0.0, (now - observed.astimezone(UTC)).total_seconds())
    stale = age > contract.max_age.total_seconds()
    return _observation(
        entity_id=entity_id,
        quality=WeatherSourceQuality.STALE if stale else WeatherSourceQuality.AVAILABLE,
        reason="source_stale" if stale else None,
        value=value,
        unit=contract.canonical_unit,
        state=state,
        now=now,
        supported_forecast_types=supported_forecast_types,
    )


def _numeric_observation(
    role: WeatherSourceRole,
    entity_id: str,
    state: State,
    *,
    now: datetime,
) -> WeatherSourceObservation:
    contract = _CONTRACTS[role]
    is_weather = entity_id.startswith("weather.")
    if is_weather:
        if contract.weather_attribute is None:
            return _observation(
                entity_id=entity_id,
                quality=WeatherSourceQuality.INCOMPLETE,
                reason="source_contract_mismatch",
                state=state,
                now=now,
            )
        raw_value = state.attributes.get(contract.weather_attribute)
        raw_unit = (
            "%"
            if role is WeatherSourceRole.RELATIVE_HUMIDITY
            else state.attributes.get(contract.weather_unit_attribute or "")
        )
    else:
        if not entity_id.startswith("sensor."):
            return _observation(
                entity_id=entity_id,
                quality=WeatherSourceQuality.INCOMPLETE,
                reason="source_contract_mismatch",
                state=state,
                now=now,
            )
        if (
            contract.sensor_device_class is not None
            and state.attributes.get("device_class") != contract.sensor_device_class
        ):
            return _observation(
                entity_id=entity_id,
                quality=WeatherSourceQuality.INCOMPLETE,
                reason="source_contract_mismatch",
                state=state,
                now=now,
            )
        if (
            contract.sensor_state_classes is not None
            and state.attributes.get("state_class") not in contract.sensor_state_classes
        ):
            return _observation(
                entity_id=entity_id,
                quality=WeatherSourceQuality.INCOMPLETE,
                reason="source_contract_mismatch",
                state=state,
                now=now,
            )
        raw_value = state.state
        raw_unit = state.attributes.get("unit_of_measurement")
    if isinstance(raw_value, bool) or not isinstance(raw_value, int | float | str):
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.INCOMPLETE,
            reason="value_missing",
            state=state,
            now=now,
        )
    try:
        numeric = float(raw_value)
    except ValueError:
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.INCOMPLETE,
            reason="value_not_numeric",
            state=state,
            now=now,
        )
    if not math.isfinite(numeric):
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.IMPLAUSIBLE,
            reason="value_not_finite",
            state=state,
            now=now,
        )
    try:
        normalized = _convert_value(role, numeric, raw_unit)
    except HomeAssistantError, ValueError:
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.INCOMPLETE,
            reason="unit_not_supported",
            state=state,
            now=now,
        )
    if (contract.minimum is not None and normalized < contract.minimum) or (
        contract.maximum is not None and normalized > contract.maximum
    ):
        return _observation(
            entity_id=entity_id,
            quality=WeatherSourceQuality.IMPLAUSIBLE,
            reason="outside_plausible_range",
            value=normalized,
            unit=contract.canonical_unit,
            state=state,
            now=now,
        )
    return _available_or_stale(
        entity_id,
        state,
        contract,
        now=now,
        value=normalized,
    )


def observe_weather_sources(
    hass: HomeAssistant,
    configured_sources: object,
    *,
    now: datetime | None = None,
) -> dict[str, dict[str, object]]:
    """Build current normalized observations for every weather-source role."""
    evaluated_at = (now or datetime.now(UTC)).astimezone(UTC)
    sources: Mapping[object, object] = (
        configured_sources if isinstance(configured_sources, Mapping) else {}
    )
    observations: dict[str, WeatherSourceObservation] = {}
    for role in WEATHER_SOURCE_ROLES:
        selected = sources.get(role.value)
        if not isinstance(selected, str) or not selected:
            observations[role.value] = _observation(
                entity_id=None,
                quality=WeatherSourceQuality.NOT_CONFIGURED,
                reason="source_not_configured",
                now=evaluated_at,
            )
            continue
        state = hass.states.get(selected)
        if state is None:
            observations[role.value] = _observation(
                entity_id=selected,
                quality=WeatherSourceQuality.UNAVAILABLE,
                reason="entity_not_found",
                now=evaluated_at,
            )
            continue
        if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            observations[role.value] = _observation(
                entity_id=selected,
                quality=WeatherSourceQuality.UNAVAILABLE,
                reason="entity_unavailable",
                state=state,
                now=evaluated_at,
            )
            continue
        observations[role.value] = (
            _forecast_observation(selected, state, now=evaluated_at)
            if role is WeatherSourceRole.FORECAST
            else _numeric_observation(role, selected, state, now=evaluated_at)
        )
    air_temperature = observations[WeatherSourceRole.AIR_TEMPERATURE]
    dew_point = observations[WeatherSourceRole.DEW_POINT]
    if (
        air_temperature.quality in {WeatherSourceQuality.AVAILABLE, WeatherSourceQuality.STALE}
        and dew_point.quality in {WeatherSourceQuality.AVAILABLE, WeatherSourceQuality.STALE}
        and air_temperature.value is not None
        and dew_point.value is not None
        and dew_point.value > air_temperature.value + 2
    ):
        observations[WeatherSourceRole.DEW_POINT] = replace(
            dew_point,
            quality=WeatherSourceQuality.IMPLAUSIBLE,
            reason="dew_point_above_temperature",
        )
    return {role: observation.as_dict() for role, observation in observations.items()}
