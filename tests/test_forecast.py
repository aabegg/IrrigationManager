"""Behavioral tests for forecast-based irrigation postponement."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.irrigation_manager.forecast import (
    ForecastPeriod,
    ForecastSettings,
    async_fetch_forecast,
    evaluate_rain_forecast,
    next_make_up_opportunity,
    normalize_forecast_periods,
    postponement_deadline,
)


def test_complete_probable_periods_can_postpone_until_next_opportunity() -> None:
    """Only complete periods meeting the probability threshold contribute."""
    settings = ForecastSettings(
        minimum_precipitation_mm=3.0,
        minimum_probability_percent=70.0,
    )
    result = evaluate_rain_forecast(
        periods=(
            ForecastPeriod(
                starts_at=datetime(2026, 7, 31, 8, tzinfo=UTC),
                ends_at=datetime(2026, 7, 31, 9, tzinfo=UTC),
                precipitation_mm=2.0,
                probability_percent=80.0,
            ),
            ForecastPeriod(
                starts_at=datetime(2026, 7, 31, 9, tzinfo=UTC),
                ends_at=datetime(2026, 7, 31, 10, tzinfo=UTC),
                precipitation_mm=1.5,
                probability_percent=75.0,
            ),
            ForecastPeriod(
                starts_at=datetime(2026, 7, 31, 10, tzinfo=UTC),
                ends_at=datetime(2026, 7, 31, 11, tzinfo=UTC),
                precipitation_mm=20.0,
                probability_percent=69.0,
            ),
            ForecastPeriod(
                starts_at=datetime(2026, 8, 1, 3, 30, tzinfo=UTC),
                ends_at=datetime(2026, 8, 1, 4, 30, tzinfo=UTC),
                precipitation_mm=20.0,
                probability_percent=100.0,
            ),
        ),
        evaluated_at=datetime(2026, 7, 31, 6, tzinfo=UTC),
        next_opportunity_at=datetime(2026, 8, 1, 4, tzinfo=UTC),
        forecast_type="hourly",
        source_entity_id="weather.home",
        settings=settings,
    )

    assert result.should_postpone is True
    assert result.qualified_precipitation_mm == pytest.approx(3.5)
    assert result.qualified_periods == (result.considered_periods[0], result.considered_periods[1])
    assert result.quality == "valid"
    assert result.reason == "forecast_threshold_reached"


def test_hourly_forecast_normalizes_units_and_rejects_incomplete_periods() -> None:
    """Do not invent probability or timing fields omitted by a provider."""
    result = normalize_forecast_periods(
        raw_forecast=(
            {
                "datetime": "2026-07-31T08:00:00+00:00",
                "precipitation": 0.1,
                "precipitation_probability": 80,
            },
            {
                "datetime": "2026-07-31T09:00:00+00:00",
                "precipitation": 0.2,
            },
            {
                "datetime": "not-a-timestamp",
                "precipitation": 1.0,
                "precipitation_probability": 90,
            },
        ),
        forecast_type="hourly",
        precipitation_unit="in",
        timezone=ZoneInfo("Europe/Zurich"),
    )

    assert result.quality == "partial"
    assert result.warnings == (
        "forecast_period_incomplete",
        "forecast_period_datetime_invalid",
    )
    assert len(result.periods) == 1
    assert result.periods[0].starts_at == datetime(2026, 7, 31, 8, tzinfo=UTC)
    assert result.periods[0].ends_at == datetime(2026, 7, 31, 9, tzinfo=UTC)
    assert result.periods[0].precipitation_mm == pytest.approx(2.54)


async def test_fetch_forecast_falls_back_to_next_supported_native_type(
    hass: HomeAssistant,
) -> None:
    """A failed preferred HA action may use the next advertised forecast type."""
    hass.states.async_set(
        "weather.home",
        "rainy",
        {"precipitation_unit": "mm"},
    )
    service_call = AsyncMock(
        side_effect=(
            HomeAssistantError("hourly unavailable"),
            {
                "weather.home": {
                    "forecast": [
                        {
                            "datetime": "2026-08-01T00:00:00+02:00",
                            "precipitation": 4.0,
                            "precipitation_probability": 85,
                        }
                    ]
                }
            },
        )
    )
    with patch("homeassistant.core.ServiceRegistry.async_call", service_call):
        result = await async_fetch_forecast(
            hass,
            entity_id="weather.home",
            supported_types=("daily", "hourly"),
            timezone=ZoneInfo("Europe/Zurich"),
        )

    assert result.quality == "valid"
    assert result.forecast_type == "daily"
    assert result.warnings == ("forecast_action_failed:hourly",)
    assert result.periods[0].precipitation_mm == pytest.approx(4.0)
    assert [call.args[:2] for call in service_call.await_args_list] == [
        ("weather", "get_forecasts"),
        ("weather", "get_forecasts"),
    ]
    assert [call.kwargs["service_data"]["type"] for call in service_call.await_args_list] == [
        "hourly",
        "daily",
    ]
    assert all(call.kwargs["blocking"] for call in service_call.await_args_list)
    assert all(call.kwargs["return_response"] for call in service_call.await_args_list)


def test_daily_forecast_rejects_period_that_does_not_start_at_local_midnight() -> None:
    """A daily value is usable only when it covers one complete local calendar day."""
    result = normalize_forecast_periods(
        raw_forecast=(
            {
                "datetime": "2026-08-01T12:00:00+02:00",
                "precipitation": 4.0,
                "precipitation_probability": 85,
            },
        ),
        forecast_type="daily",
        precipitation_unit="mm",
        timezone=ZoneInfo("Europe/Zurich"),
    )

    assert result.periods == ()
    assert result.quality == "invalid"
    assert result.warnings == ("forecast_daily_period_incomplete",)


def test_forecast_rejects_non_finite_value_after_unit_conversion() -> None:
    """An extreme but finite provider value must not overflow into a rain decision."""
    result = normalize_forecast_periods(
        raw_forecast=(
            {
                "datetime": "2026-08-01T00:00:00+00:00",
                "precipitation": 1e308,
                "precipitation_probability": 85,
            },
        ),
        forecast_type="hourly",
        precipitation_unit="in",
        timezone=ZoneInfo("Europe/Zurich"),
    )

    assert result.periods == ()
    assert result.quality == "invalid"
    assert result.warnings == ("forecast_period_unplausible",)


def test_next_make_up_opportunity_respects_cross_midnight_and_fixed_deadline() -> None:
    """Resolve local windows without extending the original deadline."""
    timezone = ZoneInfo("Europe/Zurich")
    original_end = datetime(2026, 10, 24, 5, tzinfo=timezone)
    deadline = postponement_deadline(
        original_window_end=original_end,
        maximum_days=2,
        timezone=timezone,
    )
    schedule = [
        {
            "weekday": weekday,
            "start": "23:30:00" if weekday == "sunday" else None,
            "end": "01:30:00" if weekday == "sunday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]

    opportunity = next_make_up_opportunity(
        schedule=schedule,
        after=original_end,
        deadline=deadline,
        timezone=timezone,
    )

    assert deadline == datetime(2026, 10, 26, 5, tzinfo=timezone)
    assert opportunity is not None
    assert opportunity.starts_at == datetime(2026, 10, 25, 23, 30, tzinfo=timezone)
    assert opportunity.ends_at == datetime(2026, 10, 26, 1, 30, tzinfo=timezone)
