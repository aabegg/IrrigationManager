"""Weather acquisition, unit normalization, and daily ET0 calculation."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from itertools import pairwise
from statistics import fmean
from typing import Any, cast

from aiohttp import ClientTimeout
from homeassistant.components.recorder import history as recorder_history
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.recorder import get_instance
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .const import (
    CONF_ET0_PRIORITY,
    CONF_ET0_SENSORS,
    CONF_HUMIDITY_SENSORS,
    CONF_LOCAL_WIND_HEIGHT_M,
    CONF_OPEN_METEO_ENABLED,
    CONF_PRESSURE_SENSORS,
    CONF_RAIN_SENSORS,
    CONF_SEASONAL_ET0_MM,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_SUNSHINE_DURATION_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS,
    CONF_WEATHER_WIND_HEIGHT_M,
    CONF_WIND_SPEED_SENSORS,
    ET0_PRIORITY_DIRECT,
)
from .water_balance import (
    Fao56DailyInputs,
    HargreavesDailyInputs,
    calculate_fao56_daily,
    calculate_hargreaves_daily,
)

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True, slots=True)
class WeatherValue:
    """One normalized daily value with provenance."""

    value: float
    source: str
    sample_count: int
    newest_sample: str | None
    quality: str

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible explanation fragment."""
        return {
            "value": self.value,
            "source": self.source,
            "sample_count": self.sample_count,
            "newest_sample": self.newest_sample,
            "quality": self.quality,
        }


@dataclass(frozen=True, slots=True)
class DailyWeather:
    """Best available normalized observations for one local calendar day."""

    period_id: str
    start_utc: datetime
    end_utc: datetime
    minimum_temperature_c: WeatherValue | None
    maximum_temperature_c: WeatherValue | None
    mean_temperature_c: WeatherValue | None
    mean_humidity_percent: WeatherValue | None
    wind_speed_2m_m_s: WeatherValue | None
    solar_radiation_mj_m2_day: WeatherValue | None
    sunshine_duration_hours: WeatherValue | None
    pressure_kpa: WeatherValue | None
    rain_mm: WeatherValue | None
    direct_et0_mm: WeatherValue | None

    def inputs(self) -> dict[str, object]:
        """Return all accepted and missing inputs for a calculation snapshot."""
        values = {
            "minimum_temperature_c": self.minimum_temperature_c,
            "maximum_temperature_c": self.maximum_temperature_c,
            "mean_temperature_c": self.mean_temperature_c,
            "mean_humidity_percent": self.mean_humidity_percent,
            "wind_speed_2m_m_s": self.wind_speed_2m_m_s,
            "solar_radiation_mj_m2_day": self.solar_radiation_mj_m2_day,
            "sunshine_duration_hours": self.sunshine_duration_hours,
            "pressure_kpa": self.pressure_kpa,
            "rain_mm": self.rain_mm,
            "direct_et0_mm": self.direct_et0_mm,
        }
        return {
            key: value.as_dict() if value is not None else None for key, value in values.items()
        }


@dataclass(frozen=True, slots=True)
class Et0Result:
    """Reference evapotranspiration result and complete model explanation."""

    value_mm: float | None
    method: str
    quality: str
    inputs: dict[str, object]
    comparisons: dict[str, float]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible immutable calculation snapshot."""
        return {
            "value_mm": self.value_mm,
            "method": self.method,
            "quality": self.quality,
            "inputs": self.inputs,
            "comparisons": self.comparisons,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class RainForecast:
    """Forecast rain used only to defer execution."""

    amount_mm: float
    probability_percent: float | None
    valid_at: datetime
    issued_at: datetime
    source: str
    quality: str

    def as_dict(self) -> dict[str, object]:
        """Return a safe forecast explanation."""
        return {
            "amount_mm": self.amount_mm,
            "probability_percent": self.probability_percent,
            "valid_at": self.valid_at.isoformat(),
            "issued_at": self.issued_at.isoformat(),
            "source": self.source,
            "quality": self.quality,
        }


@dataclass(frozen=True, slots=True)
class _NumericSample:
    value: float
    at: datetime
    unit: str | None
    state_class: str | None


class WeatherOrchestrator:
    """Select configured HA sources before an explicitly enabled public API."""

    def __init__(self, hass: HomeAssistant, config: Mapping[str, Any]) -> None:
        """Initialize an installation-scoped weather source selector."""
        self._hass = hass
        self._config = config

    async def async_daily_weather(self, day: date, *, end: datetime | None = None) -> DailyWeather:
        """Aggregate one local calendar day from Recorder and selected fallbacks."""
        local_start = datetime.combine(day, time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE)
        local_end = end or datetime.combine(
            day.fromordinal(day.toordinal() + 1), time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE
        )
        start_utc = local_start.astimezone(UTC)
        end_utc = local_end.astimezone(UTC)
        entity_ids = self._configured_sensor_ids()
        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if isinstance(weather_entity, str):
            entity_ids.append(weather_entity)
        histories = await self._async_history(start_utc, end_utc, entity_ids)
        open_meteo = await self._async_open_meteo(day) if self._open_meteo_enabled else None

        temperatures = self._temperature_values(histories, end_utc)
        weather_temperature = self._weather_attribute_values(
            histories, "temperature", "temperature_unit", end_utc, _temperature_c
        )
        selected_temperature = temperatures or weather_temperature
        minimum_temperature = self._stat_value(
            selected_temperature, "minimum", start=start_utc, end=end_utc
        )
        maximum_temperature = self._stat_value(
            selected_temperature, "maximum", start=start_utc, end=end_utc
        )
        mean_temperature = self._stat_value(
            selected_temperature, "mean", start=start_utc, end=end_utc
        )
        if (
            minimum_temperature is not None
            and maximum_temperature is not None
            and not (-90 <= minimum_temperature.value <= maximum_temperature.value <= 70)
        ):
            minimum_temperature = maximum_temperature = mean_temperature = None
        if minimum_temperature is None:
            minimum_temperature = _open_meteo_value(open_meteo, "temperature_2m_min")
            maximum_temperature = _open_meteo_value(open_meteo, "temperature_2m_max")
            if minimum_temperature is not None and maximum_temperature is not None:
                mean_temperature = WeatherValue(
                    value=(minimum_temperature.value + maximum_temperature.value) / 2,
                    source="open_meteo",
                    sample_count=2,
                    newest_sample=None,
                    quality="external_service",
                )

        humidity = self._first_sensor_aggregate(
            histories,
            CONF_HUMIDITY_SENSORS,
            start_utc,
            end_utc,
            _identity,
            "mean",
            minimum=0,
            maximum=100,
        ) or self._stat_value(
            self._weather_attribute_values(histories, "humidity", None, end_utc, _identity),
            "mean",
            start=start_utc,
            end=end_utc,
        )
        humidity = humidity or _open_meteo_value(open_meteo, "relative_humidity_2m_mean")
        humidity = _bounded(humidity, minimum=0, maximum=100)

        wind = self._first_sensor_aggregate(
            histories,
            CONF_WIND_SPEED_SENSORS,
            start_utc,
            end_utc,
            _speed_m_s,
            "mean",
            minimum=0,
            maximum=134,
        ) or self._stat_value(
            self._weather_attribute_values(
                histories, "wind_speed", "wind_speed_unit", end_utc, _speed_m_s
            ),
            "mean",
            start=start_utc,
            end=end_utc,
        )
        if wind is None:
            wind = _open_meteo_value(open_meteo, "wind_speed_10m_mean")
        if wind is not None:
            source_height = (
                10.0
                if wind.source == "open_meteo"
                else float(self._config.get(CONF_WEATHER_WIND_HEIGHT_M, 10))
                if wind.source == "weather_entity"
                else float(self._config.get(CONF_LOCAL_WIND_HEIGHT_M, 2))
            )
            wind = WeatherValue(
                value=wind.value * _wind_height_factor(source_height, 2),
                source=wind.source,
                sample_count=wind.sample_count,
                newest_sample=wind.newest_sample,
                quality=wind.quality,
            )
        wind = _bounded(wind, minimum=0, maximum=100)

        pressure = self._first_sensor_aggregate(
            histories,
            CONF_PRESSURE_SENSORS,
            start_utc,
            end_utc,
            _pressure_kpa,
            "mean",
            minimum=50,
            maximum=120,
        ) or self._stat_value(
            self._weather_attribute_values(
                histories, "pressure", "pressure_unit", end_utc, _pressure_kpa
            ),
            "mean",
            start=start_utc,
            end=end_utc,
        )
        pressure = pressure or _open_meteo_value(open_meteo, "surface_pressure_mean")
        pressure = _bounded(pressure, minimum=50, maximum=120)

        solar = self._first_integral(
            histories, CONF_SOLAR_RADIATION_SENSORS, start_utc, end_utc, "solar"
        )
        solar = solar or _open_meteo_value(open_meteo, "shortwave_radiation_sum")
        sunshine = self._first_integral(
            histories,
            CONF_SUNSHINE_DURATION_SENSORS,
            start_utc,
            end_utc,
            "duration",
        )
        sunshine = sunshine or _open_meteo_value(open_meteo, "sunshine_duration")
        rain = self._first_integral(histories, CONF_RAIN_SENSORS, start_utc, end_utc, "rain")
        rain = rain or _open_meteo_value(open_meteo, "rain_sum")
        direct_et0 = self._first_integral(histories, CONF_ET0_SENSORS, start_utc, end_utc, "et0")
        direct_et0 = direct_et0 or _open_meteo_value(open_meteo, "et0_fao_evapotranspiration")

        return DailyWeather(
            period_id=day.isoformat(),
            start_utc=start_utc,
            end_utc=end_utc,
            minimum_temperature_c=minimum_temperature,
            maximum_temperature_c=maximum_temperature,
            mean_temperature_c=mean_temperature,
            mean_humidity_percent=humidity,
            wind_speed_2m_m_s=wind,
            solar_radiation_mj_m2_day=solar,
            sunshine_duration_hours=sunshine,
            pressure_kpa=pressure,
            rain_mm=rain,
            direct_et0_mm=direct_et0,
        )

    def calculate_et0(self, weather: DailyWeather) -> Et0Result:
        """Apply configured direct/calculated priority and scientific fallbacks."""
        inputs = weather.inputs()
        calculations: dict[str, float] = {}
        warnings: list[str] = []
        radiation = weather.solar_radiation_mj_m2_day
        if radiation is None and weather.sunshine_duration_hours is not None:
            radiation = WeatherValue(
                value=_solar_from_sunshine(
                    latitude=self._hass.config.latitude,
                    day=weather.start_utc.astimezone(dt_util.DEFAULT_TIME_ZONE).date(),
                    sunshine_hours=weather.sunshine_duration_hours.value,
                ),
                source=weather.sunshine_duration_hours.source,
                sample_count=weather.sunshine_duration_hours.sample_count,
                newest_sample=weather.sunshine_duration_hours.newest_sample,
                quality=weather.sunshine_duration_hours.quality,
            )
            inputs["derived_solar_radiation_mj_m2_day"] = radiation.as_dict()

        if all(
            value is not None
            for value in (
                weather.minimum_temperature_c,
                weather.maximum_temperature_c,
                weather.mean_temperature_c,
                weather.mean_humidity_percent,
                weather.wind_speed_2m_m_s,
                radiation,
            )
        ):
            assert weather.minimum_temperature_c is not None
            assert weather.maximum_temperature_c is not None
            assert weather.mean_temperature_c is not None
            assert weather.mean_humidity_percent is not None
            assert weather.wind_speed_2m_m_s is not None
            assert radiation is not None
            pressure = (
                weather.pressure_kpa.value
                if weather.pressure_kpa is not None
                else _pressure_from_elevation(self._hass.config.elevation)
            )
            fao_inputs = _fao_inputs(
                minimum_temperature_c=weather.minimum_temperature_c.value,
                maximum_temperature_c=weather.maximum_temperature_c.value,
                mean_temperature_c=weather.mean_temperature_c.value,
                humidity_percent=weather.mean_humidity_percent.value,
                wind_speed_2m_m_s=weather.wind_speed_2m_m_s.value,
                solar_radiation_mj_m2_day=radiation.value,
                pressure_kpa=pressure,
                elevation_m=self._hass.config.elevation,
                latitude=self._hass.config.latitude,
                day=weather.start_utc.astimezone(dt_util.DEFAULT_TIME_ZONE).date(),
            )
            calculations["fao56"] = calculate_fao56_daily(fao_inputs)
            inputs["fao56_derived"] = {
                "saturation_vapor_pressure_kpa": fao_inputs.saturation_vapor_pressure_kpa,
                "actual_vapor_pressure_kpa": fao_inputs.actual_vapor_pressure_kpa,
                "vapor_pressure_curve_slope_kpa_c": (fao_inputs.vapor_pressure_curve_slope_kpa_c),
                "psychrometric_constant_kpa_c": fao_inputs.psychrometric_constant_kpa_c,
                "net_radiation_mj_m2_day": fao_inputs.net_radiation_mj_m2_day,
                "pressure_origin": (
                    weather.pressure_kpa.source
                    if weather.pressure_kpa is not None
                    else "elevation_estimate"
                ),
            }

        if weather.minimum_temperature_c is not None and weather.maximum_temperature_c is not None:
            ra = extraterrestrial_radiation_mj_m2_day(
                self._hass.config.latitude,
                weather.start_utc.astimezone(dt_util.DEFAULT_TIME_ZONE).date(),
            )
            calculations["hargreaves_samani"] = calculate_hargreaves_daily(
                HargreavesDailyInputs(
                    minimum_temperature_c=weather.minimum_temperature_c.value,
                    maximum_temperature_c=weather.maximum_temperature_c.value,
                    extraterrestrial_radiation_mj_m2_day=ra,
                )
            )
            inputs["extraterrestrial_radiation_mj_m2_day"] = ra

        if weather.direct_et0_mm is not None:
            calculations["direct"] = weather.direct_et0_mm.value
        priority = str(self._config.get(CONF_ET0_PRIORITY, ET0_PRIORITY_DIRECT))
        order = (
            ("direct", "fao56", "hargreaves_samani")
            if priority == ET0_PRIORITY_DIRECT
            else ("fao56", "hargreaves_samani", "direct")
        )
        method = next((candidate for candidate in order if candidate in calculations), None)
        if method is None:
            return Et0Result(None, "unavailable", "unavailable", inputs, calculations)
        if "direct" in calculations and "fao56" in calculations:
            difference = abs(calculations["direct"] - calculations["fao56"])
            inputs["direct_fao56_difference_mm"] = difference
            if difference > max(2.0, calculations["fao56"] * 0.5):
                warnings.append("direct_et0_differs_from_fao56")
        quality = {
            "direct": weather.direct_et0_mm.quality if weather.direct_et0_mm else "estimated",
            "fao56": "calculated_high",
            "hargreaves_samani": "calculated_reduced",
        }[method]
        quality_inputs = (
            (
                weather.minimum_temperature_c,
                weather.maximum_temperature_c,
                weather.mean_temperature_c,
                weather.mean_humidity_percent,
                weather.wind_speed_2m_m_s,
                radiation,
            )
            if method == "fao56"
            else (weather.minimum_temperature_c, weather.maximum_temperature_c)
            if method == "hargreaves_samani"
            else ()
        )
        if any(
            value is not None and value.quality == "observed_partial" for value in quality_inputs
        ):
            quality = "calculated_partial"
        return Et0Result(
            calculations[method], method, quality, inputs, calculations, tuple(warnings)
        )

    async def async_rain_forecast(self, now: datetime) -> RainForecast | None:
        """Return the nearest daily rain forecast without treating it as observation."""
        weather_entity = self._config.get(CONF_WEATHER_ENTITY)
        if isinstance(weather_entity, str):
            try:
                response = await self._hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"type": "daily"},
                    target={"entity_id": weather_entity},
                    blocking=True,
                    return_response=True,
                )
                entity_response = (
                    response.get(weather_entity, {}) if isinstance(response, dict) else {}
                )
                if not isinstance(entity_response, dict):
                    entity_response = {}
                forecasts = entity_response.get("forecast", [])
                state = self._hass.states.get(weather_entity)
                if isinstance(forecasts, list) and state is not None:
                    for raw in forecasts:
                        if not isinstance(raw, dict) or not isinstance(raw.get("datetime"), str):
                            continue
                        valid_at = datetime.fromisoformat(str(raw["datetime"]))
                        if valid_at.date() < now.astimezone(dt_util.DEFAULT_TIME_ZONE).date():
                            continue
                        amount = raw.get("precipitation")
                        if isinstance(amount, int | float):
                            return RainForecast(
                                amount_mm=_length_mm(
                                    float(amount),
                                    cast(str | None, state.attributes.get("precipitation_unit")),
                                ),
                                probability_percent=_optional_float(
                                    raw.get("precipitation_probability")
                                ),
                                valid_at=valid_at,
                                issued_at=state.last_reported,
                                source="weather_entity",
                                quality="forecast",
                            )
            except HomeAssistantError, ValueError, TypeError:
                pass
        if not self._open_meteo_enabled:
            return None
        local_day = now.astimezone(dt_util.DEFAULT_TIME_ZONE).date()
        open_meteo_data = await self._async_open_meteo(
            local_day,
            end_day=local_day.fromordinal(local_day.toordinal() + 3),
        )
        forecast_value = _open_meteo_rain_forecast(open_meteo_data)
        if forecast_value is None:
            return None
        valid_day, amount, probability = forecast_value
        return RainForecast(
            amount_mm=amount,
            probability_percent=probability,
            valid_at=datetime.combine(valid_day, time.min, tzinfo=dt_util.DEFAULT_TIME_ZONE),
            issued_at=dt_util.utcnow(),
            source="open_meteo",
            quality="forecast",
        )

    async def _async_history(
        self, start: datetime, end: datetime, entity_ids: Sequence[str]
    ) -> dict[str, list[State]]:
        """Read Recorder in its executor and degrade to current states when absent."""
        if not entity_ids:
            return {}
        try:
            result = await get_instance(self._hass).async_add_executor_job(
                recorder_history.get_significant_states,
                self._hass,
                start,
                end,
                list(dict.fromkeys(entity_ids)),
                None,
                True,
                False,
                False,
                False,
            )
            return {
                entity_id: [state for state in states if isinstance(state, State)]
                for entity_id, states in result.items()
            }
        except HomeAssistantError, KeyError, RuntimeError:
            current: dict[str, list[State]] = {}
            for entity_id in entity_ids:
                state = self._hass.states.get(entity_id)
                if state is not None and start <= state.last_reported <= end:
                    current[entity_id] = [state]
            return current

    @property
    def _open_meteo_enabled(self) -> bool:
        return self._config.get(CONF_OPEN_METEO_ENABLED, False) is True

    async def _async_open_meteo(
        self, day: date, *, end_day: date | None = None
    ) -> Mapping[str, object] | None:
        """Fetch credential-free daily data only after explicit opt-in."""
        params: dict[str, str | float] = {
            "latitude": self._hass.config.latitude,
            "longitude": self._hass.config.longitude,
            "timezone": self._hass.config.time_zone,
            "start_date": day.isoformat(),
            "end_date": (end_day or day).isoformat(),
            "daily": ",".join(
                (
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "shortwave_radiation_sum",
                    "sunshine_duration",
                    "rain_sum",
                    "precipitation_probability_max",
                    "et0_fao_evapotranspiration",
                )
            ),
            "wind_speed_unit": "ms",
        }
        try:
            async with async_get_clientsession(self._hass).get(
                OPEN_METEO_URL, params=params, timeout=ClientTimeout(total=20)
            ) as response:
                response.raise_for_status()
                payload = await response.json()
        except Exception:  # noqa: BLE001 - external service failures are a normal fallback case
            return None
        daily = payload.get("daily") if isinstance(payload, dict) else None
        return cast(Mapping[str, object], daily) if isinstance(daily, dict) else None

    def _configured_sensor_ids(self) -> list[str]:
        result: list[str] = []
        for key in (
            CONF_TEMPERATURE_SENSORS,
            CONF_HUMIDITY_SENSORS,
            CONF_WIND_SPEED_SENSORS,
            CONF_SOLAR_RADIATION_SENSORS,
            CONF_SUNSHINE_DURATION_SENSORS,
            CONF_PRESSURE_SENSORS,
            CONF_RAIN_SENSORS,
            CONF_ET0_SENSORS,
        ):
            result.extend(self._entity_ids(key))
        return list(dict.fromkeys(result))

    def _entity_ids(self, key: str) -> list[str]:
        value = self._config.get(key, [])
        if isinstance(value, str):
            return [value]
        if isinstance(value, list | tuple):
            return [item for item in value if isinstance(item, str)]
        return []

    def _temperature_values(
        self, histories: Mapping[str, Sequence[State]], end: datetime
    ) -> list[tuple[_NumericSample, str]]:
        for entity_id in self._entity_ids(CONF_TEMPERATURE_SENSORS):
            values = self._numeric_samples(histories.get(entity_id, ()), end, _temperature_c)
            if values and all(-90 <= value.value <= 70 for value in values):
                return [(value, entity_id) for value in values]
        return []

    def _first_sensor_aggregate(
        self,
        histories: Mapping[str, Sequence[State]],
        key: str,
        start: datetime,
        end: datetime,
        converter: Any,
        statistic: str,
        minimum: float = -math.inf,
        maximum: float = math.inf,
    ) -> WeatherValue | None:
        for entity_id in self._entity_ids(key):
            values = self._numeric_samples(histories.get(entity_id, ()), end, converter)
            result = self._stat_value(
                [(value, entity_id) for value in values],
                statistic,
                start=start,
                end=end,
            )
            if result is not None and minimum <= result.value <= maximum:
                return result
        return None

    def _first_integral(
        self,
        histories: Mapping[str, Sequence[State]],
        key: str,
        start: datetime,
        end: datetime,
        kind: str,
    ) -> WeatherValue | None:
        for entity_id in self._entity_ids(key):
            samples = self._raw_numeric_samples(histories.get(entity_id, ()), end)
            value = _daily_integral(samples, kind=kind, start=start, end=end)
            maximum = 1_000 if kind in {"rain", "et0"} else 1_000_000
            if value is not None and math.isfinite(value) and 0 <= value <= maximum:
                return WeatherValue(
                    value=value,
                    source=entity_id,
                    sample_count=len(samples),
                    newest_sample=samples[-1].at.isoformat(),
                    quality="observed",
                )
        return None

    def _weather_attribute_values(
        self,
        histories: Mapping[str, Sequence[State]],
        attribute: str,
        unit_attribute: str | None,
        end: datetime,
        converter: Any,
    ) -> list[tuple[_NumericSample, str]]:
        entity_id = self._config.get(CONF_WEATHER_ENTITY)
        if not isinstance(entity_id, str):
            return []
        result: list[tuple[_NumericSample, str]] = []
        for state in histories.get(entity_id, ()):
            raw = state.attributes.get(attribute)
            if isinstance(raw, bool) or not isinstance(raw, int | float):
                continue
            unit = state.attributes.get(unit_attribute) if unit_attribute else None
            try:
                value = converter(float(raw), unit if isinstance(unit, str) else None)
            except TypeError, ValueError:
                continue
            if math.isfinite(value):
                result.append(
                    (
                        _NumericSample(value, state.last_reported, None, None),
                        "weather_entity",
                    )
                )
        if result and self._fresh(max(sample.at for sample, _ in result), end):
            return result
        return []

    def _numeric_samples(
        self, states: Sequence[State], end: datetime, converter: Any
    ) -> list[_NumericSample]:
        result: list[_NumericSample] = []
        for sample in self._raw_numeric_samples(states, end):
            try:
                value = converter(sample.value, sample.unit)
            except TypeError, ValueError:
                continue
            if math.isfinite(value):
                result.append(_NumericSample(value, sample.at, None, sample.state_class))
        return result

    def _raw_numeric_samples(self, states: Sequence[State], end: datetime) -> list[_NumericSample]:
        result: list[_NumericSample] = []
        for state in states:
            if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
                continue
            try:
                value = float(state.state)
            except ValueError:
                continue
            if not math.isfinite(value):
                continue
            unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
            state_class = state.attributes.get("state_class")
            result.append(
                _NumericSample(
                    value,
                    state.last_reported,
                    unit if isinstance(unit, str) else None,
                    state_class if isinstance(state_class, str) else None,
                )
            )
        result.sort(key=lambda item: item.at)
        return result if result and self._fresh(result[-1].at, end) else []

    def _fresh(self, newest: datetime, end: datetime) -> bool:
        max_age_hours = float(self._config.get(CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS, 6))
        return (end - newest).total_seconds() <= max_age_hours * 3600

    @staticmethod
    def _stat_value(
        values: Sequence[tuple[_NumericSample, str]],
        statistic: str,
        *,
        start: datetime,
        end: datetime,
    ) -> WeatherValue | None:
        if not values:
            return None
        numeric = [sample.value for sample, _ in values]
        if statistic == "minimum":
            value = min(numeric)
        elif statistic == "maximum":
            value = max(numeric)
        else:
            weighted_total = 0.0
            covered_seconds = 0.0
            ordered = sorted((sample for sample, _ in values), key=lambda sample: sample.at)
            for index, sample in enumerate(ordered):
                interval_start = max(start, sample.at)
                interval_end = min(end, ordered[index + 1].at if index + 1 < len(ordered) else end)
                seconds = max(0.0, (interval_end - interval_start).total_seconds())
                weighted_total += sample.value * seconds
                covered_seconds += seconds
            value = weighted_total / covered_seconds if covered_seconds else fmean(numeric)
        newest = max(sample.at for sample, _ in values)
        oldest = min(sample.at for sample, _ in values)
        covered = (end - max(start, oldest)).total_seconds()
        total = max(1.0, (end - start).total_seconds())
        quality = "observed" if covered / total >= 0.75 else "observed_partial"
        return WeatherValue(value, values[0][1], len(values), newest.isoformat(), quality)


def calculate_seasonal_value(values: str | Sequence[float], day: date) -> float:
    """Interpolate a cyclic twelve-month curve at the middle of each month."""
    if isinstance(values, str):
        points = [float(item.strip()) for item in values.split(",")]
    else:
        points = [float(item) for item in values]
    if len(points) != 12 or not all(math.isfinite(value) and value >= 0 for value in points):
        raise ValueError("A seasonal curve requires twelve finite non-negative monthly values")
    month_index = day.month - 1
    days_in_month = (
        date(day.year + (day.month == 12), day.month % 12 + 1, 1) - date(day.year, day.month, 1)
    ).days
    fraction = (day.day - 0.5) / days_in_month
    if fraction < 0.5:
        previous = points[(month_index - 1) % 12]
        return previous + (points[month_index] - previous) * (fraction + 0.5)
    following = points[(month_index + 1) % 12]
    return points[month_index] + (following - points[month_index]) * (fraction - 0.5)


def seasonal_et0(config: Mapping[str, Any], day: date) -> float | None:
    """Return an explicitly configured seasonal ET0 replacement."""
    raw = config.get(CONF_SEASONAL_ET0_MM)
    if not isinstance(raw, str | list | tuple):
        return None
    try:
        return calculate_seasonal_value(raw, day)
    except TypeError, ValueError:
        return None


def extraterrestrial_radiation_mj_m2_day(latitude: float, day: date) -> float:
    """Return FAO-56 extraterrestrial radiation for a latitude and day."""
    latitude_rad = math.radians(max(-90.0, min(90.0, latitude)))
    day_number = day.timetuple().tm_yday
    inverse_distance = 1 + 0.033 * math.cos(2 * math.pi * day_number / 365)
    solar_declination = 0.409 * math.sin(2 * math.pi * day_number / 365 - 1.39)
    sunset_angle = math.acos(
        max(-1.0, min(1.0, -math.tan(latitude_rad) * math.tan(solar_declination)))
    )
    return (
        24
        * 60
        / math.pi
        * 0.0820
        * inverse_distance
        * (
            sunset_angle * math.sin(latitude_rad) * math.sin(solar_declination)
            + math.cos(latitude_rad) * math.cos(solar_declination) * math.sin(sunset_angle)
        )
    )


def _fao_inputs(
    *,
    minimum_temperature_c: float,
    maximum_temperature_c: float,
    mean_temperature_c: float,
    humidity_percent: float,
    wind_speed_2m_m_s: float,
    solar_radiation_mj_m2_day: float,
    pressure_kpa: float,
    elevation_m: float,
    latitude: float,
    day: date,
) -> Fao56DailyInputs:
    es_min = _saturation_vapor_pressure(minimum_temperature_c)
    es_max = _saturation_vapor_pressure(maximum_temperature_c)
    saturation = (es_min + es_max) / 2
    actual = saturation * min(100.0, max(0.0, humidity_percent)) / 100
    slope = (
        4098 * _saturation_vapor_pressure(mean_temperature_c) / (mean_temperature_c + 237.3) ** 2
    )
    psychrometric = 0.000665 * pressure_kpa
    ra = extraterrestrial_radiation_mj_m2_day(latitude, day)
    clear_sky = max(0.0001, (0.75 + 0.00002 * elevation_m) * ra)
    net_shortwave = 0.77 * solar_radiation_mj_m2_day
    cloud_factor = max(0.05, 1.35 * min(1.0, solar_radiation_mj_m2_day / clear_sky) - 0.35)
    net_longwave = (
        4.903e-9
        * (((maximum_temperature_c + 273.16) ** 4 + (minimum_temperature_c + 273.16) ** 4) / 2)
        * (0.34 - 0.14 * math.sqrt(max(0.0, actual)))
        * cloud_factor
    )
    return Fao56DailyInputs(
        mean_temperature_c=mean_temperature_c,
        wind_speed_2m_m_s=max(0.0, wind_speed_2m_m_s),
        saturation_vapor_pressure_kpa=saturation,
        actual_vapor_pressure_kpa=actual,
        vapor_pressure_curve_slope_kpa_c=slope,
        psychrometric_constant_kpa_c=psychrometric,
        net_radiation_mj_m2_day=net_shortwave - net_longwave,
    )


def _daily_integral(
    samples: Sequence[_NumericSample], *, kind: str, start: datetime, end: datetime
) -> float | None:
    if not samples:
        return None
    unit = samples[-1].unit or ""
    if kind == "solar" and unit in {"W/m²", "W/m2", "kW/m²", "kW/m2"}:
        multiplier = 1000 if unit.startswith("kW") else 1
        joules = 0.0
        for index, sample in enumerate(samples):
            next_at = samples[index + 1].at if index + 1 < len(samples) else end
            sample_at = max(start, sample.at)
            joules += (
                max(0.0, sample.value)
                * multiplier
                * max(0.0, (next_at - sample_at).total_seconds())
            )
        return joules / 1_000_000
    if kind == "rain" and unit in {"mm/h", "in/h"}:
        total = 0.0
        for index, sample in enumerate(samples):
            next_at = samples[index + 1].at if index + 1 < len(samples) else end
            sample_at = max(start, sample.at)
            rate_mm_h = sample.value if unit == "mm/h" else sample.value * 25.4
            total += max(0.0, rate_mm_h) * max(0.0, (next_at - sample_at).total_seconds()) / 3600
        return total
    if kind == "duration" and unit in {"s", "min", "h"}:
        if len(samples) < 2 and samples[-1].state_class in {"total", "total_increasing"}:
            return None
        return _counter_delta(samples) * {"s": 1 / 3600, "min": 1 / 60, "h": 1}[unit]
    if kind in {"rain", "et0"}:
        if len(samples) < 2 and samples[-1].state_class in {"total", "total_increasing"}:
            return None
        delta = _counter_delta(samples) if len(samples) > 1 else samples[-1].value
        if kind == "et0" and unit in {"mm/d", "mm/day"}:
            return delta
        if kind == "et0" and unit in {"in/d", "in/day"}:
            return delta * 25.4
        return _length_mm(delta, unit)
    if kind == "solar" and unit in {"MJ/m²", "MJ/m2", "kWh/m²", "kWh/m2", "Wh/m²", "Wh/m2"}:
        if len(samples) < 2 and samples[-1].state_class in {"total", "total_increasing"}:
            return None
        delta = _counter_delta(samples) if len(samples) > 1 else samples[-1].value
        if unit.startswith("kWh"):
            return delta * 3.6
        if unit.startswith("Wh"):
            return delta * 0.0036
        return delta
    return None


def _counter_delta(samples: Sequence[_NumericSample]) -> float:
    total = 0.0
    for previous, current in pairwise(samples):
        total += (
            current.value - previous.value if current.value >= previous.value else current.value
        )
    return max(0.0, total)


def _open_meteo_value(data: Mapping[str, object] | None, key: str) -> WeatherValue | None:
    value = _open_meteo_number(data, key)
    if value is None:
        return None
    if key == "sunshine_duration":
        value /= 3600
    if key == "surface_pressure_mean":
        value /= 10
    return WeatherValue(value, "open_meteo", 1, None, "external_service")


def _open_meteo_number(data: Mapping[str, object] | None, key: str) -> float | None:
    if data is None:
        return None
    raw = data.get(key)
    if (
        not isinstance(raw, list)
        or not raw
        or isinstance(raw[0], bool)
        or not isinstance(raw[0], int | float)
    ):
        return None
    value = float(raw[0])
    return value if math.isfinite(value) else None


def _open_meteo_rain_forecast(
    data: Mapping[str, object] | None,
) -> tuple[date, float, float | None] | None:
    """Return the first non-zero valid daily Open-Meteo rain forecast."""
    if data is None:
        return None
    days = data.get("time")
    amounts = data.get("rain_sum")
    probabilities = data.get("precipitation_probability_max")
    if not isinstance(days, list) or not isinstance(amounts, list):
        return None
    probability_values = probabilities if isinstance(probabilities, list) else []
    for index, (raw_day, raw_amount) in enumerate(zip(days, amounts, strict=False)):
        if (
            not isinstance(raw_day, str)
            or isinstance(raw_amount, bool)
            or not isinstance(raw_amount, int | float)
        ):
            continue
        amount = float(raw_amount)
        if not math.isfinite(amount) or amount <= 0:
            continue
        probability = (
            _optional_float(probability_values[index]) if index < len(probability_values) else None
        )
        try:
            return date.fromisoformat(raw_day), amount, probability
        except ValueError:
            continue
    return None


def _temperature_c(value: float, unit: str | None) -> float:
    return TemperatureConverter.convert(
        value, unit or UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS
    )


def _speed_m_s(value: float, unit: str | None) -> float:
    return SpeedConverter.convert(
        value, unit or UnitOfSpeed.METERS_PER_SECOND, UnitOfSpeed.METERS_PER_SECOND
    )


def _pressure_kpa(value: float, unit: str | None) -> float:
    return PressureConverter.convert(value, unit or UnitOfPressure.HPA, UnitOfPressure.KPA)


def _length_mm(value: float, unit: str | None) -> float:
    return DistanceConverter.convert(
        value, unit or UnitOfLength.MILLIMETERS, UnitOfLength.MILLIMETERS
    )


def _identity(value: float, _unit: str | None) -> float:
    return value


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def _bounded(value: WeatherValue | None, *, minimum: float, maximum: float) -> WeatherValue | None:
    return value if value is not None and minimum <= value.value <= maximum else None


def _wind_height_factor(source_height_m: float, target_height_m: float) -> float:
    if target_height_m != 2 or math.isclose(source_height_m, 2):
        return 1.0
    return 4.87 / math.log(67.8 * source_height_m - 5.42)


def _pressure_from_elevation(elevation_m: float) -> float:
    return float(101.3 * ((293 - 0.0065 * elevation_m) / 293) ** 5.26)


def _saturation_vapor_pressure(temperature_c: float) -> float:
    return 0.6108 * math.exp(17.27 * temperature_c / (temperature_c + 237.3))


def _solar_from_sunshine(*, latitude: float, day: date, sunshine_hours: float) -> float:
    ra = extraterrestrial_radiation_mj_m2_day(latitude, day)
    latitude_rad = math.radians(latitude)
    declination = 0.409 * math.sin(2 * math.pi * day.timetuple().tm_yday / 365 - 1.39)
    sunset_angle = math.acos(max(-1.0, min(1.0, -math.tan(latitude_rad) * math.tan(declination))))
    daylight = 24 / math.pi * sunset_angle
    return (0.25 + 0.5 * min(1.0, max(0.0, sunshine_hours / max(daylight, 0.01)))) * ra
