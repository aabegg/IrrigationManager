"""Evapotranspiration and zone water-balance calculations."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Fao56DailyInputs:
    """Validated daily inputs for FAO-56 Penman-Monteith."""

    mean_temperature_c: float
    wind_speed_2m_m_s: float
    saturation_vapor_pressure_kpa: float
    actual_vapor_pressure_kpa: float
    vapor_pressure_curve_slope_kpa_c: float
    psychrometric_constant_kpa_c: float
    net_radiation_mj_m2_day: float
    soil_heat_flux_mj_m2_day: float = 0.0


@dataclass(frozen=True, slots=True)
class HargreavesDailyInputs:
    """Daily temperature inputs for Hargreaves-Samani."""

    minimum_temperature_c: float
    maximum_temperature_c: float
    extraterrestrial_radiation_mj_m2_day: float


@dataclass(frozen=True, slots=True)
class ZoneWaterBalance:
    """Final water deficit for one irrigation zone."""

    deficit_mm: float
    maximum_deficit_mm: float


@dataclass(frozen=True, slots=True)
class WaterBalancePeriod:
    """Finalized contributions for one accounting period."""

    crop_evapotranspiration_mm: float
    effective_rain_mm: float
    effective_irrigation_mm: float


def calculate_fao56_daily(inputs: Fao56DailyInputs) -> float:
    """Return daily reference evapotranspiration in millimeters per day."""
    radiation_term = (
        0.408
        * inputs.vapor_pressure_curve_slope_kpa_c
        * (inputs.net_radiation_mj_m2_day - inputs.soil_heat_flux_mj_m2_day)
    )
    aerodynamic_term = (
        inputs.psychrometric_constant_kpa_c
        * (900 / (inputs.mean_temperature_c + 273))
        * inputs.wind_speed_2m_m_s
        * (inputs.saturation_vapor_pressure_kpa - inputs.actual_vapor_pressure_kpa)
    )
    denominator = inputs.vapor_pressure_curve_slope_kpa_c + (
        inputs.psychrometric_constant_kpa_c * (1 + 0.34 * inputs.wind_speed_2m_m_s)
    )
    return max(0.0, (radiation_term + aerodynamic_term) / denominator)


def calculate_hargreaves_daily(inputs: HargreavesDailyInputs) -> float:
    """Return daily reference evapotranspiration in millimeters per day."""
    mean_temperature_c = (inputs.minimum_temperature_c + inputs.maximum_temperature_c) / 2
    temperature_range_c = max(0.0, inputs.maximum_temperature_c - inputs.minimum_temperature_c)
    return float(
        0.0023
        * 0.408
        * inputs.extraterrestrial_radiation_mj_m2_day
        * (mean_temperature_c + 17.8)
        * temperature_range_c**0.5
    )


def apply_water_balance(balance: ZoneWaterBalance, period: WaterBalancePeriod) -> ZoneWaterBalance:
    """Apply finalized weather and irrigation contributions to a zone."""
    updated_deficit_mm = (
        balance.deficit_mm
        + period.crop_evapotranspiration_mm
        - period.effective_rain_mm
        - period.effective_irrigation_mm
    )
    return ZoneWaterBalance(
        deficit_mm=min(balance.maximum_deficit_mm, max(0.0, updated_deficit_mm)),
        maximum_deficit_mm=balance.maximum_deficit_mm,
    )


def calculate_irrigation_target_liters(
    *, deficit_mm: float, area_m2: float, application_efficiency: float
) -> float:
    """Convert a net zone deficit to the required gross irrigation volume."""
    if not 0 < application_efficiency <= 1:
        msg = "application_efficiency must be greater than 0 and at most 1"
        raise ValueError(msg)
    return max(0.0, deficit_mm) * max(0.0, area_m2) / application_efficiency
