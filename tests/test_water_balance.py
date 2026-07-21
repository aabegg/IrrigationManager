"""Behavior tests for evapotranspiration and the water balance."""

import pytest

from custom_components.irrigation_manager.water_balance import (
    Fao56DailyInputs,
    HargreavesDailyInputs,
    WaterBalancePeriod,
    ZoneWaterBalance,
    apply_water_balance,
    calculate_fao56_daily,
    calculate_hargreaves_daily,
    calculate_irrigation_target_liters,
)


def test_calculate_fao56_daily_matches_fao_example_18() -> None:
    """Calculate the published FAO-56 Example 18 reference value."""
    inputs = Fao56DailyInputs(
        mean_temperature_c=16.9,
        wind_speed_2m_m_s=2.078,
        saturation_vapor_pressure_kpa=1.997,
        actual_vapor_pressure_kpa=1.409,
        vapor_pressure_curve_slope_kpa_c=0.122,
        psychrometric_constant_kpa_c=0.0666,
        net_radiation_mj_m2_day=13.28,
        soil_heat_flux_mj_m2_day=0.0,
    )

    assert calculate_fao56_daily(inputs) == pytest.approx(3.88, abs=0.01)


def test_calculate_hargreaves_daily_uses_radiation_in_mj() -> None:
    """Calculate Hargreaves-Samani from the FAO Example 18 weather data."""
    inputs = HargreavesDailyInputs(
        minimum_temperature_c=12.3,
        maximum_temperature_c=21.5,
        extraterrestrial_radiation_mj_m2_day=41.08837556,
    )

    assert calculate_hargreaves_daily(inputs) == pytest.approx(4.0582, abs=0.005)


def test_apply_water_balance_clamps_deficit_to_soil_capacity() -> None:
    """Keep the zone deficit within zero and the modeled soil capacity."""
    balance = ZoneWaterBalance(deficit_mm=18.0, maximum_deficit_mm=25.0)

    dry_period = WaterBalancePeriod(
        crop_evapotranspiration_mm=10.0,
        effective_rain_mm=1.0,
        effective_irrigation_mm=0.0,
    )
    wet_period = WaterBalancePeriod(
        crop_evapotranspiration_mm=1.0,
        effective_rain_mm=40.0,
        effective_irrigation_mm=0.0,
    )

    assert apply_water_balance(balance, dry_period).deficit_mm == 25.0
    assert apply_water_balance(balance, wet_period).deficit_mm == 0.0


def test_calculate_irrigation_target_accounts_for_application_efficiency() -> None:
    """Convert net millimeters to gross liters using application efficiency."""
    assert calculate_irrigation_target_liters(
        deficit_mm=12.0,
        area_m2=20.0,
        application_efficiency=0.8,
    ) == pytest.approx(300.0)
