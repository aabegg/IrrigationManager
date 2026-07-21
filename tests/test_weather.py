"""Weather source selection, normalization, and model orchestration tests."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant, State, SupportsResponse

from custom_components.irrigation_manager.const import (
    CONF_ET0_PRIORITY,
    CONF_ET0_SENSORS,
    CONF_HUMIDITY_SENSORS,
    CONF_LOCAL_WIND_HEIGHT_M,
    CONF_OPEN_METEO_ENABLED,
    CONF_PRESSURE_SENSORS,
    CONF_RAIN_SENSORS,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS,
    CONF_WIND_SPEED_SENSORS,
    ET0_PRIORITY_CALCULATED,
    ET0_PRIORITY_DIRECT,
)
from custom_components.irrigation_manager.water_balance import calculate_effective_rain
from custom_components.irrigation_manager.weather import (
    OPEN_METEO_URL,
    WeatherOrchestrator,
    calculate_seasonal_value,
)


def _state(
    entity_id: str,
    value: float,
    at: datetime,
    *,
    unit: str,
    state_class: str = "measurement",
) -> State:
    return State(
        entity_id,
        str(value),
        {"unit_of_measurement": unit, "state_class": state_class},
        last_changed=at,
        last_reported=at,
        last_updated=at,
    )


async def test_daily_sources_are_prioritized_normalized_and_aggregated(
    hass: HomeAssistant,
) -> None:
    """Prefer the first fresh local source and normalize all model units."""
    config = {
        CONF_TEMPERATURE_SENSORS: ["sensor.stale_temperature", "sensor.temperature"],
        CONF_HUMIDITY_SENSORS: ["sensor.humidity"],
        CONF_WIND_SPEED_SENSORS: ["sensor.wind"],
        CONF_LOCAL_WIND_HEIGHT_M: 10,
        CONF_SOLAR_RADIATION_SENSORS: ["sensor.solar"],
        CONF_PRESSURE_SENSORS: ["sensor.pressure"],
        CONF_RAIN_SENSORS: ["sensor.rain"],
        CONF_ET0_SENSORS: ["sensor.et0"],
        CONF_ET0_PRIORITY: ET0_PRIORITY_DIRECT,
        CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS: 6,
    }
    orchestrator = WeatherOrchestrator(hass, config)
    start = datetime(2026, 7, 20, 7, tzinfo=UTC)
    noon = datetime(2026, 7, 20, 19, tzinfo=UTC)
    late = datetime(2026, 7, 21, 5, tzinfo=UTC)
    history = {
        "sensor.stale_temperature": [_state("sensor.stale_temperature", 100, late, unit="°C")],
        "sensor.temperature": [
            _state("sensor.temperature", 50, start, unit="°F"),
            _state("sensor.temperature", 68, noon, unit="°F"),
            _state("sensor.temperature", 59, late, unit="°F"),
        ],
        "sensor.humidity": [_state("sensor.humidity", 50, late, unit="%")],
        "sensor.wind": [_state("sensor.wind", 36, late, unit="km/h")],
        "sensor.solar": [
            _state("sensor.solar", 100, start, unit="W/m²"),
            _state("sensor.solar", 100, noon, unit="W/m²"),
            _state("sensor.solar", 100, late, unit="W/m²"),
        ],
        "sensor.pressure": [_state("sensor.pressure", 1013, late, unit="hPa")],
        "sensor.rain": [
            _state("sensor.rain", 1, start, unit="mm", state_class="total_increasing"),
            _state("sensor.rain", 4, late, unit="mm", state_class="total_increasing"),
        ],
        "sensor.et0": [_state("sensor.et0", 4.2, late, unit="mm")],
    }

    with patch.object(orchestrator, "_async_history", AsyncMock(return_value=history)):
        weather = await orchestrator.async_daily_weather(date(2026, 7, 20))

    assert weather.minimum_temperature_c is not None
    assert weather.maximum_temperature_c is not None
    assert weather.mean_temperature_c is not None
    assert weather.minimum_temperature_c.value == pytest.approx(10)
    assert weather.maximum_temperature_c.value == pytest.approx(20)
    assert weather.mean_temperature_c.value == pytest.approx(14.583, abs=0.001)
    assert weather.mean_temperature_c.source == "sensor.temperature"
    assert weather.wind_speed_2m_m_s is not None
    assert weather.wind_speed_2m_m_s.value == pytest.approx(7.48, rel=0.01)
    assert weather.pressure_kpa is not None
    assert weather.pressure_kpa.value == pytest.approx(101.3)
    assert weather.solar_radiation_mj_m2_day is not None
    assert weather.solar_radiation_mj_m2_day.value == pytest.approx(8.64)
    assert weather.rain_mm is not None
    assert weather.rain_mm.value == pytest.approx(3)

    result = orchestrator.calculate_et0(weather)
    assert result.method == "direct"
    assert result.value_mm == pytest.approx(4.2)
    assert "fao56" in result.comparisons


async def test_recorder_acquisition_path_reads_history_without_mocking_orchestrator(
    hass: HomeAssistant,
) -> None:
    """Traverse the production Recorder adapter and normalize its returned states."""
    orchestrator = WeatherOrchestrator(
        hass,
        {
            CONF_TEMPERATURE_SENSORS: ["sensor.temperature"],
            CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS: 6,
        },
    )
    start = datetime(2026, 7, 20, 7, tzinfo=UTC)
    late = datetime(2026, 7, 21, 5, tzinfo=UTC)
    history = {
        "sensor.temperature": [
            _state("sensor.temperature", 10, start, unit="°C"),
            _state("sensor.temperature", 20, late, unit="°C"),
        ]
    }

    class Recorder:
        async def async_add_executor_job(self, target: Any, *args: Any) -> Any:
            return target(*args)

    with (
        patch(
            "custom_components.irrigation_manager.weather.get_instance",
            return_value=Recorder(),
        ),
        patch(
            "custom_components.irrigation_manager.weather.recorder_history.get_significant_states",
            return_value=history,
        ) as get_history,
    ):
        weather = await orchestrator.async_daily_weather(date(2026, 7, 20))

    assert get_history.call_count == 1
    assert weather.minimum_temperature_c is not None
    assert weather.minimum_temperature_c.value == 10


async def test_weather_service_forecast_acquisition_path(hass: HomeAssistant) -> None:
    """Use the production HA weather service response path for rain deferral data."""
    entity_id = "weather.garden"
    issued_at = datetime.now(UTC)
    hass.states.async_set(entity_id, "rainy", {"precipitation_unit": "in"})

    async def get_forecasts(_call: Any) -> dict[str, object]:
        return {
            entity_id: {
                "forecast": [
                    {
                        "datetime": (issued_at + timedelta(days=1)).isoformat(),
                        "precipitation": 0.5,
                        "precipitation_probability": 80,
                    }
                ]
            }
        }

    hass.services.async_register(
        "weather",
        "get_forecasts",
        get_forecasts,
        supports_response=SupportsResponse.ONLY,
    )
    orchestrator = WeatherOrchestrator(hass, {"weather_entity": entity_id})

    forecast = await orchestrator.async_rain_forecast(issued_at)

    assert forecast is not None
    assert forecast.amount_mm == pytest.approx(12.7)
    assert forecast.probability_percent == 80
    assert forecast.source == "weather_entity"


async def test_open_meteo_acquisition_path_uses_no_credentials_or_real_network(
    hass: HomeAssistant,
) -> None:
    """Traverse the opt-in HTTP adapter using a deterministic fake HA client session."""
    payload = {
        "daily": {
            "time": ["2026-07-20"],
            "temperature_2m_min": [12.0],
            "temperature_2m_max": [24.0],
            "shortwave_radiation_sum": [18.0],
            "sunshine_duration": [28_800],
            "rain_sum": [3.0],
            "precipitation_probability_max": [75],
            "et0_fao_evapotranspiration": [4.5],
        }
    }

    class Response:
        async def __aenter__(self) -> Response:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        def raise_for_status(self) -> None:
            return None

        async def json(self) -> dict[str, object]:
            return payload

    class Session:
        requested_url: str | None = None
        requested_params: dict[str, object] | None = None

        def get(self, url: str, **kwargs: Any) -> Response:
            self.requested_url = url
            self.requested_params = kwargs.get("params")
            return Response()

    session = Session()
    orchestrator = WeatherOrchestrator(hass, {CONF_OPEN_METEO_ENABLED: True})
    with patch(
        "custom_components.irrigation_manager.weather.async_get_clientsession",
        return_value=session,
    ):
        weather = await orchestrator.async_daily_weather(date(2026, 7, 20))

    assert session.requested_url == OPEN_METEO_URL
    assert session.requested_params is not None
    assert "apikey" not in session.requested_params
    assert weather.direct_et0_mm is not None
    assert weather.direct_et0_mm.value == 4.5
    assert weather.rain_mm is not None
    assert weather.rain_mm.value == 3


async def test_local_wind_defaults_to_two_meter_measurement_height(
    hass: HomeAssistant,
) -> None:
    """Do not normalize local wind unless its configured physical height differs."""
    orchestrator = WeatherOrchestrator(
        hass,
        {
            CONF_WIND_SPEED_SENSORS: ["sensor.wind"],
            CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS: 6,
        },
    )
    at = datetime(2026, 7, 21, 5, tzinfo=UTC)
    history = {"sensor.wind": [_state("sensor.wind", 10, at, unit="m/s")]}
    with patch.object(orchestrator, "_async_history", AsyncMock(return_value=history)):
        weather = await orchestrator.async_daily_weather(date(2026, 7, 20))

    assert weather.wind_speed_2m_m_s is not None
    assert weather.wind_speed_2m_m_s.value == 10


async def test_hargreaves_is_used_when_fao_inputs_are_incomplete(hass: HomeAssistant) -> None:
    """Use the reduced-data model rather than inventing humidity, wind, or radiation."""
    orchestrator = WeatherOrchestrator(
        hass,
        {
            CONF_TEMPERATURE_SENSORS: ["sensor.temperature"],
            CONF_ET0_PRIORITY: ET0_PRIORITY_CALCULATED,
            CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS: 6,
        },
    )
    start = datetime(2026, 7, 20, 7, tzinfo=UTC)
    at = datetime(2026, 7, 21, 5, tzinfo=UTC)
    history = {
        "sensor.temperature": [
            _state("sensor.temperature", 12, start, unit="°C"),
            _state("sensor.temperature", 25, at, unit="°C"),
        ]
    }

    with patch.object(orchestrator, "_async_history", AsyncMock(return_value=history)):
        weather = await orchestrator.async_daily_weather(date(2026, 7, 20))
    result = orchestrator.calculate_et0(weather)

    assert result.method == "hargreaves_samani"
    assert result.quality == "calculated_reduced"
    assert result.value_mm is not None
    assert "fao56" not in result.comparisons


def test_seasonal_curve_and_effective_rain_are_bounded() -> None:
    """Interpolate annual factors and expose runoff/drainage instead of hiding excess rain."""
    curve = "1,2,3,4,5,6,7,8,9,10,11,12"
    assert calculate_seasonal_value(curve, date(2026, 1, 16)) == pytest.approx(1, abs=0.1)

    rain = calculate_effective_rain(
        measured_rain_mm=30,
        rain_factor=0.8,
        maximum_infiltration_mm=20,
        available_storage_mm=12,
    )
    assert rain.effective_mm == 12
    assert rain.runoff_mm == 4
    assert rain.drainage_mm == 8
