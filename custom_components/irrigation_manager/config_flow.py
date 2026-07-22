"""Config and subentry flows for Irrigation Manager."""

import json
from datetime import date, time
from typing import Any, override
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import (
    CONF_NAME,
    Platform,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TimeSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ACTUATOR_FEEDBACK_MAX_AGE_SECONDS,
    CONF_ACTUATOR_TRANSITION_GRACE_SECONDS,
    CONF_AGRONOMIC_VALUES_CONFIRMED,
    CONF_APPLICATION_EFFICIENCY,
    CONF_AREA_M2,
    CONF_AUTOMATIC_MAX_DURATION,
    CONF_AUTOMATION_ENABLED,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_CROP_FACTOR,
    CONF_CUSTOM_PROFILES,
    CONF_DEFAULT_DURATION,
    CONF_ET0_PRIORITY,
    CONF_ET0_SENSORS,
    CONF_EXPOSURE_PROFILE,
    CONF_EXTERNAL_BLOCK,
    CONF_EXTERNAL_FAILURE_POLICY,
    CONF_EXTERNAL_MAX_AGE_SECONDS,
    CONF_EXTERNAL_PERMIT,
    CONF_FLOW_GRACE_SECONDS,
    CONF_FLOW_MAX_AGE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_FORECAST_DEFERRAL_HOURS,
    CONF_FORECAST_RAIN_PROBABILITY,
    CONF_FORECAST_RAIN_THRESHOLD_MM,
    CONF_FROST_ENTITY,
    CONF_FROST_THRESHOLD,
    CONF_HARDWARE_BATTERY_MINIMUM,
    CONF_HARDWARE_BATTERY_SENSOR,
    CONF_HARDWARE_CONNECTIVITY_SENSOR,
    CONF_HARDWARE_FAULT_SENSOR,
    CONF_HARDWARE_HEALTH_MAX_AGE_SECONDS,
    CONF_HUMIDITY_SENSORS,
    CONF_INSTALLATION_DAILY_BUDGET_LITERS,
    CONF_INSTALLATION_MAX_DELIVERY_RUNTIME,
    CONF_INSTALLATION_MAX_OPERATION_LIFETIME,
    CONF_INSTALLATION_WEEKLY_BUDGET_LITERS,
    CONF_IRRIGATION_PROFILE,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_LITERS_PER_COUNT,
    CONF_LOCAL_WIND_HEIGHT_M,
    CONF_MAIN_VALVE,
    CONF_MAIN_VALVE_FEEDBACK,
    CONF_MAINTENANCE_CONFIRMATION_INTERVAL,
    CONF_MAINTENANCE_MAX_DURATION,
    CONF_MAINTENANCE_TASKS,
    CONF_MANDATORY_AMOUNT_LITERS,
    CONF_MAX_DELIVERY_RUNTIME,
    CONF_MAX_DOSE_AMOUNT,
    CONF_MAX_DOSE_DURATION,
    CONF_MAX_EFFECTIVE_RAIN_MM,
    CONF_MAX_FLOW,
    CONF_MAX_OPERATION_LIFETIME,
    CONF_MAXIMUM_DEFICIT_MM,
    CONF_MAXIMUM_INTERVAL_DAYS,
    CONF_MAXIMUM_TARGET_LITERS,
    CONF_METER_FAILURE_STRATEGY,
    CONF_METER_MAX_AGE_SECONDS,
    CONF_METER_RESOLUTION_LITERS,
    CONF_MIN_FLOW,
    CONF_MINIMUM_EFFECTIVE_LITERS,
    CONF_MINIMUM_INTERVAL_DAYS,
    CONF_MINIMUM_TRIGGER_LITERS,
    CONF_NOTIFY_ENTITIES,
    CONF_OPEN_METEO_ENABLED,
    CONF_PAUSE_TIMEOUT_SECONDS,
    CONF_PLANT_PROFILE,
    CONF_PRESSURE_SENSORS,
    CONF_PROFILE_OVERRIDES,
    CONF_RAIN_FACTOR,
    CONF_RAIN_SENSORS,
    CONF_RAIN_STOP_ENTITY,
    CONF_RAIN_STOP_THRESHOLD,
    CONF_RAW_METER,
    CONF_SEASONAL_CROP_FACTORS,
    CONF_SEASONAL_ET0_MM,
    CONF_SOAK_DURATION,
    CONF_SOIL_MOISTURE_AGGREGATION,
    CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM,
    CONF_SOIL_MOISTURE_MAX_AGE_SECONDS,
    CONF_SOIL_MOISTURE_ROLE,
    CONF_SOIL_MOISTURE_SENSORS,
    CONF_SOIL_MOISTURE_WET_THRESHOLD,
    CONF_SOIL_PROFILE,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_SPRING_CHECKLIST,
    CONF_SUBAREAS,
    CONF_SUNSHINE_DURATION_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    CONF_WATER_METER,
    CONF_WATER_TARIFF_PER_M3,
    CONF_WATERING_MODE,
    CONF_WATERING_WINDOWS,
    CONF_WEATHER_BACKFILL_DAYS,
    CONF_WEATHER_ENTITY,
    CONF_WEATHER_FAILURE_POLICY,
    CONF_WEATHER_FALLBACK_DAYS,
    CONF_WEATHER_FINALIZATION_TIME,
    CONF_WEATHER_MAX_AGE_SECONDS,
    CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS,
    CONF_WEATHER_PREVIEW_INTERVAL_HOURS,
    CONF_WEATHER_WIND_HEIGHT_M,
    CONF_WIND_INTERLOCK_ENTITY,
    CONF_WIND_INTERLOCK_THRESHOLD,
    CONF_WIND_MANUAL_POLICY,
    CONF_WIND_SPEED_SENSORS,
    CONF_WINTER_REMINDER_DATE,
    CONF_ZONE_DAILY_BUDGET_LITERS,
    CONF_ZONE_PRIORITY,
    CONF_ZONE_VALVE,
    CONF_ZONE_VALVE_FEEDBACK,
    CONF_ZONE_WEEKLY_BUDGET_LITERS,
    DOMAIN,
    ET0_PRIORITY_CALCULATED,
    ET0_PRIORITY_DIRECT,
    EXTERNAL_FAILURE_FAIL_SAFE,
    METER_FAILURE_ABORT,
    METER_FAILURE_ESTIMATED_TIME_FALLBACK,
    SOIL_MOISTURE_ROLE_CORRECTION,
    SOIL_MOISTURE_ROLE_INHIBIT,
    SOIL_MOISTURE_ROLE_PLAUSIBILITY,
    SUBENTRY_TYPE_ZONE,
    WATERING_MODE_DEMAND,
    WATERING_MODE_MINIMUM,
    WEATHER_FAILURE_FAIL_SAFE,
    WIND_MANUAL_ALLOW,
    WIND_MANUAL_BLOCK,
)
from .manager import IrrigationManager
from .profiles import (
    dependent_profile_ids,
    profile_impacted_zones,
    resolve_effective_zone_profile,
    validate_custom_profiles,
)
from .scheduler import parse_window_rule
from .weather import calculate_seasonal_value

ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"

INSTALLATION_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Optional(CONF_MAIN_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_MAIN_VALVE_FEEDBACK): EntitySelector(
            EntitySelectorConfig(domain=[Platform.BINARY_SENSOR, Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_WATER_METER): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_RAW_METER): EntitySelector(EntitySelectorConfig(domain=Platform.SENSOR)),
        vol.Optional(CONF_LITERS_PER_COUNT): NumberSelector(
            NumberSelectorConfig(min=0.001, max=1_000_000, step=0.001, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_METER_RESOLUTION_LITERS): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=1_000_000,
                step=0.001,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_METER_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=86_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_LEAK_MONITORING, default=True): BooleanSelector(),
        vol.Optional(CONF_LEAK_FLOW_THRESHOLD, default=0.5): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_LEAK_DURATION_SECONDS, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_FLOW_MAX_AGE_SECONDS, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.WEATHER)
        ),
        vol.Optional(CONF_TEMPERATURE_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_HUMIDITY_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_WIND_SPEED_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_LOCAL_WIND_HEIGHT_M, default=2): NumberSelector(
            NumberSelectorConfig(min=0.5, max=30, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WEATHER_WIND_HEIGHT_M, default=10): NumberSelector(
            NumberSelectorConfig(min=0.5, max=30, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SOLAR_RADIATION_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_SUNSHINE_DURATION_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_PRESSURE_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_RAIN_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_ET0_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(CONF_ET0_PRIORITY, default=ET0_PRIORITY_DIRECT): SelectSelector(
            SelectSelectorConfig(
                options=[ET0_PRIORITY_DIRECT, ET0_PRIORITY_CALCULATED],
                translation_key=CONF_ET0_PRIORITY,
            )
        ),
        vol.Optional(CONF_OPEN_METEO_ENABLED, default=False): BooleanSelector(),
        vol.Optional(CONF_WEATHER_OBSERVATION_MAX_AGE_HOURS, default=6): NumberSelector(
            NumberSelectorConfig(min=1, max=72, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WEATHER_FALLBACK_DAYS, default=3): NumberSelector(
            NumberSelectorConfig(min=0, max=30, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WEATHER_BACKFILL_DAYS, default=14): NumberSelector(
            NumberSelectorConfig(min=1, max=365, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_SEASONAL_ET0_MM, default="1.0,1.5,2.5,3.5,4.5,5.0,5.5,5.0,3.5,2.5,1.5,1.0"
        ): TextSelector(),
        vol.Optional(CONF_WEATHER_FINALIZATION_TIME, default="00:10:00"): TimeSelector(),
        vol.Optional(CONF_WEATHER_PREVIEW_INTERVAL_HOURS, default=1): NumberSelector(
            NumberSelectorConfig(min=1, max=12, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FROST_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_FROST_THRESHOLD, default=2): NumberSelector(
            NumberSelectorConfig(
                min=-50,
                max=20,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTemperature.CELSIUS,
            )
        ),
        vol.Optional(CONF_RAIN_STOP_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_RAIN_STOP_THRESHOLD, default=0.1): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WEATHER_MAX_AGE_SECONDS, default=900): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=86_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(
            CONF_WEATHER_FAILURE_POLICY, default=WEATHER_FAILURE_FAIL_SAFE
        ): SelectSelector(
            SelectSelectorConfig(
                options=[WEATHER_FAILURE_FAIL_SAFE],
                translation_key=CONF_WEATHER_FAILURE_POLICY,
            )
        ),
        vol.Optional(CONF_INSTALLATION_MAX_DELIVERY_RUNTIME, default=14_400): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=604_800,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_INSTALLATION_MAX_OPERATION_LIFETIME, default=86_400): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=2_592_000,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_INSTALLATION_DAILY_BUDGET_LITERS): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=10_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_INSTALLATION_WEEKLY_BUDGET_LITERS): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=100_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_WATER_TARIFF_PER_M3): NumberSelector(
            NumberSelectorConfig(min=0, max=100_000, step=0.001, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_AUTOMATION_ENABLED, default=True): BooleanSelector(),
        vol.Optional(CONF_WINTER_REMINDER_DATE, default="10-15"): TextSelector(),
        vol.Optional(CONF_MAINTENANCE_TASKS, default=[]): ObjectSelector(),
        vol.Optional(CONF_SPRING_CHECKLIST, default=[]): ObjectSelector(),
        vol.Optional(CONF_PAUSE_TIMEOUT_SECONDS, default=3600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=604_800,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_ACTUATOR_TRANSITION_GRACE_SECONDS, default=5): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                max=60,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_ACTUATOR_FEEDBACK_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(min=1, max=86_400, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_EXTERNAL_PERMIT): EntitySelector(
            EntitySelectorConfig(domain=Platform.BINARY_SENSOR)
        ),
        vol.Optional(CONF_EXTERNAL_BLOCK): EntitySelector(
            EntitySelectorConfig(domain=Platform.BINARY_SENSOR)
        ),
        vol.Optional(CONF_EXTERNAL_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(min=1, max=86_400, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_EXTERNAL_FAILURE_POLICY, default=EXTERNAL_FAILURE_FAIL_SAFE
        ): SelectSelector(
            SelectSelectorConfig(
                options=[EXTERNAL_FAILURE_FAIL_SAFE],
                translation_key=CONF_EXTERNAL_FAILURE_POLICY,
            )
        ),
        vol.Optional(CONF_NOTIFY_ENTITIES, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.NOTIFY, multiple=True)
        ),
        vol.Optional(CONF_MAINTENANCE_MAX_DURATION, default=300): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=3600,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MAINTENANCE_CONFIRMATION_INTERVAL, default=30): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=300,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_CALIBRATION_SETTLE_SECONDS, default=2): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=60,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_CUSTOM_PROFILES, default={}): ObjectSelector(),
    }
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_ZONE_VALVE): EntitySelector(
            EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_ZONE_VALVE_FEEDBACK): EntitySelector(
            EntitySelectorConfig(domain=[Platform.BINARY_SENSOR, Platform.SWITCH, Platform.VALVE])
        ),
        vol.Optional(CONF_EXTERNAL_PERMIT): EntitySelector(
            EntitySelectorConfig(domain=Platform.BINARY_SENSOR)
        ),
        vol.Optional(CONF_EXTERNAL_BLOCK): EntitySelector(
            EntitySelectorConfig(domain=Platform.BINARY_SENSOR)
        ),
        vol.Optional(CONF_EXTERNAL_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(min=1, max=86_400, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_EXTERNAL_FAILURE_POLICY, default=EXTERNAL_FAILURE_FAIL_SAFE
        ): SelectSelector(
            SelectSelectorConfig(
                options=[EXTERNAL_FAILURE_FAIL_SAFE],
                translation_key=CONF_EXTERNAL_FAILURE_POLICY,
            )
        ),
        vol.Optional(CONF_WIND_INTERLOCK_ENTITY): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_WIND_INTERLOCK_THRESHOLD): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                max=100,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
            )
        ),
        vol.Optional(CONF_WIND_MANUAL_POLICY, default=WIND_MANUAL_ALLOW): SelectSelector(
            SelectSelectorConfig(
                options=[WIND_MANUAL_ALLOW, WIND_MANUAL_BLOCK],
                translation_key=CONF_WIND_MANUAL_POLICY,
            )
        ),
        vol.Required(CONF_DEFAULT_DURATION, default=600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MIN_FLOW): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_MAX_FLOW): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=10_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
            )
        ),
        vol.Optional(CONF_FLOW_GRACE_SECONDS, default=5): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=300,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_METER_FAILURE_STRATEGY, default=METER_FAILURE_ABORT): SelectSelector(
            SelectSelectorConfig(
                options=[METER_FAILURE_ABORT, METER_FAILURE_ESTIMATED_TIME_FALLBACK],
                translation_key=CONF_METER_FAILURE_STRATEGY,
            )
        ),
        vol.Optional(CONF_MAX_DOSE_AMOUNT): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=1_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_MAX_DOSE_DURATION): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_SOAK_DURATION, default=0): NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=86_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_AUTOMATION_ENABLED, default=False): BooleanSelector(),
        vol.Optional(CONF_WATERING_MODE, default=WATERING_MODE_DEMAND): SelectSelector(
            SelectSelectorConfig(
                options=[WATERING_MODE_DEMAND, WATERING_MODE_MINIMUM],
                translation_key=CONF_WATERING_MODE,
            )
        ),
        vol.Optional(CONF_AGRONOMIC_VALUES_CONFIRMED, default=False): BooleanSelector(),
        vol.Optional(
            CONF_PLANT_PROFILE, default="builtin:plant:generic-neutral:v1"
        ): TextSelector(),
        vol.Optional(
            CONF_SOIL_PROFILE, default="builtin:soil:generic-reference:v1"
        ): TextSelector(),
        vol.Optional(
            CONF_EXPOSURE_PROFILE, default="builtin:exposure:generic-neutral:v1"
        ): TextSelector(),
        vol.Optional(
            CONF_IRRIGATION_PROFILE, default="builtin:irrigation:generic-reference:v1"
        ): TextSelector(),
        vol.Optional(CONF_SUBAREAS, default=[]): ObjectSelector(),
        vol.Optional(CONF_PROFILE_OVERRIDES, default={}): ObjectSelector(),
        vol.Optional(CONF_AREA_M2, default=1): NumberSelector(
            NumberSelectorConfig(min=0.1, max=100_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_APPLICATION_EFFICIENCY, default=0.8): NumberSelector(
            NumberSelectorConfig(min=0.01, max=1, step=0.01, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_CROP_FACTOR, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=5, step=0.05, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_RAIN_FACTOR, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1, step=0.05, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAX_EFFECTIVE_RAIN_MM, default=25): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(
            CONF_SEASONAL_CROP_FACTORS,
            default="1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0",
        ): TextSelector(),
        vol.Optional(CONF_FORECAST_RAIN_THRESHOLD_MM, default=5): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FORECAST_RAIN_PROBABILITY, default=70): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_FORECAST_DEFERRAL_HOURS, default=24): NumberSelector(
            NumberSelectorConfig(min=0, max=168, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_DEFICIT_MM, default=50): NumberSelector(
            NumberSelectorConfig(min=0.1, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_INTERVAL_DAYS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=365, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_INTERVAL_DAYS, default=7): NumberSelector(
            NumberSelectorConfig(min=0.1, max=365, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_TRIGGER_LITERS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MANDATORY_AMOUNT_LITERS, default=1): NumberSelector(
            NumberSelectorConfig(min=0, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MINIMUM_EFFECTIVE_LITERS, default=0.1): NumberSelector(
            NumberSelectorConfig(min=0.001, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_MAXIMUM_TARGET_LITERS, default=1_000): NumberSelector(
            NumberSelectorConfig(min=0.001, max=1_000_000, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_AUTOMATIC_MAX_DURATION, default=3600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=14_400,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MAX_DELIVERY_RUNTIME, default=3_600): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=604_800,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_MAX_OPERATION_LIFETIME, default=14_400): NumberSelector(
            NumberSelectorConfig(
                min=1,
                max=2_592_000,
                step=1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfTime.SECONDS,
            )
        ),
        vol.Optional(CONF_ZONE_PRIORITY, default=0): NumberSelector(
            NumberSelectorConfig(min=-100, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WATERING_WINDOWS, default=["04:00-06:00"]): TextSelector(
            {"multiple": True}
        ),
        vol.Optional(CONF_ZONE_DAILY_BUDGET_LITERS): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=1_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_ZONE_WEEKLY_BUDGET_LITERS): NumberSelector(
            NumberSelectorConfig(
                min=0.001,
                max=10_000_000,
                step=0.1,
                mode=NumberSelectorMode.BOX,
                unit_of_measurement=UnitOfVolume.LITERS,
            )
        ),
        vol.Optional(CONF_SOIL_MOISTURE_SENSORS, default=[]): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
        ),
        vol.Optional(
            CONF_SOIL_MOISTURE_ROLE, default=SOIL_MOISTURE_ROLE_PLAUSIBILITY
        ): SelectSelector(
            SelectSelectorConfig(
                options=[
                    SOIL_MOISTURE_ROLE_PLAUSIBILITY,
                    SOIL_MOISTURE_ROLE_INHIBIT,
                    SOIL_MOISTURE_ROLE_CORRECTION,
                ],
                translation_key=CONF_SOIL_MOISTURE_ROLE,
            )
        ),
        vol.Optional(CONF_SOIL_MOISTURE_AGGREGATION, default="median"): SelectSelector(
            SelectSelectorConfig(
                options=["minimum", "median", "mean"],
                translation_key=CONF_SOIL_MOISTURE_AGGREGATION,
            )
        ),
        vol.Optional(CONF_SOIL_MOISTURE_MAX_AGE_SECONDS, default=3600): NumberSelector(
            NumberSelectorConfig(min=1, max=604_800, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SOIL_MOISTURE_WET_THRESHOLD, default=80): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM, default=0): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=0.1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_HARDWARE_BATTERY_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=Platform.SENSOR)
        ),
        vol.Optional(CONF_HARDWARE_BATTERY_MINIMUM, default=20): NumberSelector(
            NumberSelectorConfig(min=0, max=100, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_HARDWARE_CONNECTIVITY_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=[Platform.BINARY_SENSOR, Platform.SENSOR])
        ),
        vol.Optional(CONF_HARDWARE_FAULT_SENSOR): EntitySelector(
            EntitySelectorConfig(domain=[Platform.BINARY_SENSOR, Platform.SENSOR])
        ),
        vol.Optional(CONF_HARDWARE_HEALTH_MAX_AGE_SECONDS, default=300): NumberSelector(
            NumberSelectorConfig(min=1, max=86_400, step=1, mode=NumberSelectorMode.BOX)
        ),
    }
)


def _validate_zone_input(user_input: dict[str, Any], custom_profiles: object = None) -> str | None:
    """Return a form error for invalid interval/window automation settings."""
    try:
        windows = user_input.get(CONF_WATERING_WINDOWS, [])
        if not isinstance(windows, list) or not windows:
            raise ValueError
        for value in windows:
            parse_window_rule(value)
        if float(user_input[CONF_MAXIMUM_INTERVAL_DAYS]) < float(
            user_input[CONF_MINIMUM_INTERVAL_DAYS]
        ):
            return "invalid_intervals"
        calculate_seasonal_value(str(user_input[CONF_SEASONAL_CROP_FACTORS]), dt_util.now().date())
        if user_input.get(CONF_AUTOMATION_ENABLED) and not all(
            isinstance(user_input.get(key), int | float) and float(user_input[key]) > 0
            for key in (CONF_MIN_FLOW, CONF_MAX_FLOW)
        ):
            return "automation_requires_flow_profile"
        if user_input.get(CONF_AUTOMATION_ENABLED) and not user_input.get(
            CONF_AGRONOMIC_VALUES_CONFIRMED, False
        ):
            return "agronomic_confirmation_required"
    except KeyError, TypeError, ValueError:
        return "invalid_watering_windows"
    try:
        resolve_effective_zone_profile(user_input, custom_profiles, dt_util.now().date())
    except TypeError, ValueError:
        return "invalid_profiles"
    if (
        user_input.get(CONF_SOIL_MOISTURE_ROLE) == SOIL_MOISTURE_ROLE_CORRECTION
        and float(user_input.get(CONF_SOIL_MOISTURE_CORRECTION_LIMIT_MM, 0)) <= 0
    ):
        return "soil_moisture_correction_limit_required"
    if bool(user_input.get(CONF_WIND_INTERLOCK_ENTITY)) != bool(
        user_input.get(CONF_WIND_INTERLOCK_THRESHOLD)
    ):
        return "wind_interlock_requires_source_and_threshold"
    return None


def _validate_installation_input(user_input: dict[str, Any]) -> str | None:
    """Validate weather fallback and scheduling settings before persisting them."""
    try:
        calculate_seasonal_value(str(user_input[CONF_SEASONAL_ET0_MM]), dt_util.now().date())
        time.fromisoformat(str(user_input[CONF_WEATHER_FINALIZATION_TIME]))
    except TypeError, ValueError:
        return "invalid_weather_curve"
    try:
        validate_custom_profiles(user_input.get(CONF_CUSTOM_PROFILES, {}))
    except TypeError, ValueError:
        return "invalid_profiles"
    cumulative = user_input.get(CONF_WATER_METER)
    raw = user_input.get(CONF_RAW_METER)
    factor = user_input.get(CONF_LITERS_PER_COUNT)
    if cumulative and raw:
        return "multiple_meter_sources"
    if bool(raw) != bool(factor):
        return "raw_meter_requires_factor"
    if user_input.get(CONF_MAIN_VALVE_FEEDBACK) and not user_input.get(CONF_MAIN_VALVE):
        return "main_feedback_requires_main_valve"
    try:
        date.fromisoformat(f"2000-{user_input.get(CONF_WINTER_REMINDER_DATE, '10-15')}")
        _validate_maintenance_configuration(user_input)
    except TypeError, ValueError:
        return "invalid_maintenance_configuration"
    return None


def _validate_maintenance_configuration(user_input: dict[str, Any]) -> None:
    """Validate stable task/checklist IDs and recurrence fields from object selectors."""
    tasks = user_input.get(CONF_MAINTENANCE_TASKS, [])
    checklist = user_input.get(CONF_SPRING_CHECKLIST, [])
    if not isinstance(tasks, list) or not isinstance(checklist, list):
        raise ValueError
    task_ids: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError
        task_id = task.get("id")
        if (
            not isinstance(task_id, str)
            or not task_id
            or task_id in task_ids
            or not isinstance(task.get("name"), str)
            or isinstance(task.get("interval_days"), bool)
            or not isinstance(task.get("interval_days"), int | float)
            or float(task["interval_days"]) <= 0
            or not isinstance(task.get("first_due"), str)
        ):
            raise ValueError
        date.fromisoformat(str(task["first_due"]))
        task_ids.add(task_id)
    checklist_ids = [item.get("id") for item in checklist if isinstance(item, dict)]
    if (
        len(checklist_ids) != len(checklist)
        or any(
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or not item["id"]
            or not isinstance(item.get("name"), str)
            for item in checklist
        )
        or len(set(checklist_ids)) != len(checklist_ids)
    ):
        raise ValueError


class IrrigationManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure irrigation installations."""

    VERSION = 1
    MINOR_VERSION = 5

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the installation and zone expert settings flow."""
        return IrrigationManagerOptionsFlow()

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Create one physical irrigation installation."""
        if user_input is not None:
            if error := _validate_installation_input(user_input):
                return self.async_show_form(
                    step_id="user", data_schema=INSTALLATION_SCHEMA, errors={"base": error}
                )
            await self.async_set_unique_id(uuid4().hex)
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(step_id="user", data_schema=INSTALLATION_SCHEMA)

    @classmethod
    @callback
    @override
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported repeatable child configurations."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlow}


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Create and reconfigure one irrigation zone."""

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a zone to the parent irrigation installation."""
        if user_input is not None:
            if error := _validate_zone_input(
                user_input, self._get_entry().data.get(CONF_CUSTOM_PROFILES, {})
            ):
                return self.async_show_form(
                    step_id="user", data_schema=ZONE_SCHEMA, errors={"base": error}
                )
            if self._valve_is_configured(user_input[CONF_ZONE_VALVE]):
                return self.async_abort(reason="already_configured")
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                unique_id=uuid4().hex,
            )

        return self.async_show_form(step_id="user", data_schema=ZONE_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Update an existing zone without changing its stable identity."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            if error := _validate_zone_input(user_input, entry.data.get(CONF_CUSTOM_PROFILES, {})):
                return self.async_show_form(
                    step_id="reconfigure",
                    data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, user_input),
                    errors={"base": error},
                )
            if self._valve_is_configured(
                user_input[CONF_ZONE_VALVE],
                excluding_subentry_id=subentry.subentry_id,
            ):
                return self.async_abort(reason="already_configured")
            return self.async_update_and_abort(
                entry,
                subentry,
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                ZONE_SCHEMA,
                subentry.data,
            ),
        )

    def _valve_is_configured(
        self, valve_entity_id: str, excluding_subentry_id: str | None = None
    ) -> bool:
        """Return whether another zone already owns the logical valve."""
        return any(
            subentry.subentry_id != excluding_subentry_id
            and subentry.data.get(CONF_ZONE_VALVE) == valve_entity_id
            for subentry in self._get_entry().subentries.values()
        )


class IrrigationManagerOptionsFlow(OptionsFlow):
    """Edit installation and zone expert settings after setup."""

    def __init__(self) -> None:
        """Initialize transient zone selection."""
        self._zone_subentry_id: str | None = None
        self._pending_installation_input: dict[str, Any] | None = None
        self._profile_impact_names = ""
        self._installation_config_hash: str | None = None
        self._pending_import: dict[str, Any] | None = None
        self._import_preview = ""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer installation and zone settings."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["installation", "zone", "import_config"],
        )

    async def async_step_import_config(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate a portable file and show a dry-run preview before overwrite."""
        if user_input is not None:
            manager = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if not isinstance(manager, IrrigationManager):
                return self.async_abort(reason="installation_not_loaded")
            try:
                preview = await manager.async_import_portable_config(
                    payload=user_input["payload"],
                    entity_remapping=user_input.get("entity_remapping", {}),
                    zone_remapping=user_input.get("zone_remapping", {}),
                    dry_run=True,
                    confirm_overwrite=False,
                    expected_config_hash=None,
                )
            except HomeAssistantError:
                return self.async_show_form(
                    step_id="import_config",
                    data_schema=self._import_schema(),
                    errors={"base": "invalid_import"},
                )
            self._pending_import = {**user_input, "config_hash": preview["config_hash"]}
            self._import_preview = json.dumps(preview, sort_keys=True)
            return await self.async_step_import_confirm()
        return self.async_show_form(step_id="import_config", data_schema=self._import_schema())

    async def async_step_import_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require an explicit confirmation of the exact previewed entry hash."""
        if self._pending_import is None:
            return self.async_abort(reason="import_not_pending")
        if user_input is not None:
            if user_input.get("confirm_overwrite") is not True:
                self._pending_import = None
                return await self.async_step_init()
            manager = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if not isinstance(manager, IrrigationManager):
                return self.async_abort(reason="installation_not_loaded")
            pending = self._pending_import
            self._pending_import = None
            try:
                await manager.async_import_portable_config(
                    payload=pending["payload"],
                    entity_remapping=pending.get("entity_remapping", {}),
                    zone_remapping=pending.get("zone_remapping", {}),
                    dry_run=False,
                    confirm_overwrite=True,
                    expected_config_hash=pending["config_hash"],
                )
            except HomeAssistantError:
                return self.async_abort(reason="configuration_changed")
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="import_confirm",
            data_schema=vol.Schema(
                {vol.Required("confirm_overwrite", default=False): BooleanSelector()}
            ),
            description_placeholders={"preview": self._import_preview},
        )

    @staticmethod
    def _import_schema() -> vol.Schema:
        """Return selectors for portable data and explicit remapping objects."""
        return vol.Schema(
            {
                vol.Required("payload"): ObjectSelector(),
                vol.Optional("entity_remapping", default={}): ObjectSelector(),
                vol.Optional("zone_remapping", default={}): ObjectSelector(),
            }
        )

    async def async_step_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update installation sources, safety thresholds, and notifications."""
        if user_input is not None:
            if error := _validate_installation_input(user_input):
                return self.async_show_form(
                    step_id="installation",
                    data_schema=self.add_suggested_values_to_schema(
                        INSTALLATION_SCHEMA, user_input
                    ),
                    errors={"base": error},
                )
            previous_profiles = validate_custom_profiles(
                self.config_entry.data.get(CONF_CUSTOM_PROFILES, {})
            )
            next_profiles = validate_custom_profiles(user_input.get(CONF_CUSTOM_PROFILES, {}))
            changed_ids = {
                profile_id
                for profile_id in previous_profiles.keys() | next_profiles.keys()
                if previous_profiles.get(profile_id) != next_profiles.get(profile_id)
            }
            if changed_ids:
                affected_ids: set[str] = set()
                for profile_id in changed_ids:
                    affected_ids.update(dependent_profile_ids(next_profiles, profile_id))
                    affected_ids.update(dependent_profile_ids(previous_profiles, profile_id))
                impacted = profile_impacted_zones(
                    [
                        (
                            subentry.unique_id or subentry.subentry_id,
                            subentry.title,
                            subentry.data,
                        )
                        for subentry in self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
                    ],
                    affected_ids,
                )
                self._pending_installation_input = user_input
                self._profile_impact_names = ", ".join(item["name"] for item in impacted) or "none"
                return await self.async_step_profile_impact()
            return await self._save_installation(user_input)
        self._installation_config_hash = IrrigationManager.installation_config_hash(
            self.config_entry.data
        )
        return self.async_show_form(
            step_id="installation",
            data_schema=self.add_suggested_values_to_schema(
                INSTALLATION_SCHEMA,
                self.config_entry.data,
            ),
        )

    async def async_step_profile_impact(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require confirmation after showing zones affected by profile changes."""
        if self._pending_installation_input is None:
            return self.async_abort(reason="profile_change_not_pending")
        if user_input is not None:
            if user_input.get("confirm_profile_changes") is not True:
                self._pending_installation_input = None
                return await self.async_step_installation()
            pending = self._pending_installation_input
            self._pending_installation_input = None
            return await self._save_installation(pending)
        return self.async_show_form(
            step_id="profile_impact",
            data_schema=vol.Schema(
                {vol.Required("confirm_profile_changes", default=False): BooleanSelector()}
            ),
            description_placeholders={"zones": self._profile_impact_names},
        )

    async def _save_installation(self, user_input: dict[str, Any]) -> ConfigFlowResult:
        """Persist validated installation settings after any impact confirmation."""
        expected_hash = self._installation_config_hash
        if expected_hash is None:
            return self.async_abort(reason="configuration_changed")
        manager = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        try:
            if isinstance(manager, IrrigationManager):
                await manager.async_update_installation_config(
                    user_input, expected_config_hash=expected_hash
                )
            else:
                if expected_hash != IrrigationManager.installation_config_hash(
                    self.config_entry.data
                ):
                    return self.async_abort(reason="configuration_changed")
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=str(user_input[CONF_NAME]),
                    data=user_input,
                )
        except HomeAssistantError:
            return self.async_abort(reason="configuration_changed")
        return self.async_create_entry(data={})

    async def async_step_zone(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Select a zone whose expert settings should be edited."""
        zones = self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        if not zones:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            self._zone_subentry_id = str(user_input[ATTR_ZONE_SUBENTRY_ID])
            return await self.async_step_zone_settings()
        return self.async_show_form(
            step_id="zone",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_ZONE_SUBENTRY_ID): SelectSelector(
                        SelectSelectorConfig(options=[subentry.subentry_id for subentry in zones])
                    )
                }
            ),
        )

    async def async_step_zone_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Validate and update all expert settings for the selected zone."""
        subentry = self.config_entry.subentries.get(self._zone_subentry_id or "")
        if subentry is None or subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            return self.async_abort(reason="zone_not_found")
        if user_input is not None:
            if error := _validate_zone_input(
                user_input, self.config_entry.data.get(CONF_CUSTOM_PROFILES, {})
            ):
                return self.async_show_form(
                    step_id="zone_settings",
                    data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, user_input),
                    errors={"base": error},
                )
            if any(
                other.subentry_id != subentry.subentry_id
                and other.data.get(CONF_ZONE_VALVE) == user_input[CONF_ZONE_VALVE]
                for other in self.config_entry.subentries.values()
            ):
                return self.async_abort(reason="already_configured")
            self.hass.config_entries.async_update_subentry(
                self.config_entry,
                subentry,
                title=str(user_input[CONF_NAME]),
                data=user_input,
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="zone_settings",
            data_schema=self.add_suggested_values_to_schema(ZONE_SCHEMA, subentry.data),
        )
