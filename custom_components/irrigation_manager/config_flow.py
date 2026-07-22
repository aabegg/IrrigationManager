"""Config and subentry flows for Irrigation Manager."""

import asyncio
import json
from collections.abc import Mapping, Sequence
from datetime import date, time
from typing import Any, cast, override
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryData,
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
    CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED,
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
    CONF_PHENOLOGY_STAGE_SCHEDULE,
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
    EXPORT_SCHEMA_VERSION,
    EXTERNAL_FAILURE_FAIL_SAFE,
    METER_FAILURE_ABORT,
    METER_FAILURE_ESTIMATED_TIME_FALLBACK,
    PROFILE_CATALOG_VERSION,
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
    BUILTIN_PROFILES,
    dependent_profile_ids,
    profile_impacted_zones,
    profile_select_options,
    profile_selection_summary,
    resolve_effective_zone_profile,
    selection_requires_confirmation,
    validate_custom_profiles,
)
from .scheduler import parse_window_rule
from .weather import calculate_seasonal_value

ATTR_ZONE_SUBENTRY_ID = "zone_subentry_id"
_IMPORT_CREATE_LOCK = asyncio.Lock()

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
        vol.Optional(CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED, default=False): BooleanSelector(),
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
        vol.Optional(CONF_PHENOLOGY_STAGE_SCHEDULE, default={}): ObjectSelector(),
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


def _zone_schema(custom_profiles: object, language: str) -> vol.Schema:
    """Replace profile ID text boxes with source-annotated catalog selectors."""
    kinds = {
        CONF_PLANT_PROFILE: "plant",
        CONF_SOIL_PROFILE: "soil",
        CONF_EXPOSURE_PROFILE: "exposure",
        CONF_IRRIGATION_PROFILE: "irrigation",
    }
    schema: dict[object, object] = {}
    for key, selector in ZONE_SCHEMA.schema.items():
        kind = kinds.get(str(key))
        schema[key] = (
            SelectSelector(
                SelectSelectorConfig(
                    options=cast(Any, profile_select_options(custom_profiles, kind, language))
                )
            )
            if kind is not None
            else selector
        )
    return vol.Schema(schema)


def _profile_preview(
    data: Mapping[str, Any], custom_profiles: object, language: str
) -> tuple[str, bool]:
    """Return a compact profile-impact preview and whether confirmation is required."""
    summary = profile_selection_summary(data, custom_profiles, dt_util.now().date(), language)
    profiles = cast(list[dict[str, object]], summary["profiles"])
    preview = json.dumps(
        {
            "profiles": [
                {
                    "name": profile["name"],
                    "ranges": profile["ranges"],
                    "confidence": profile["confidence"],
                    "sources": _profile_source_ids(profile["sources"]),
                    "assumptions": profile["assumptions"],
                }
                for profile in profiles
            ],
            "resolved_total_available_water_mm": summary["total_available_water_mm"],
            "resolved_readily_available_water_mm": summary["readily_available_water_mm"],
            "water_limit_origin": summary["water_limit_origin"],
            "legacy_water_limit": summary["legacy_water_limit"],
            "warnings": summary["warnings"],
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    return preview, selection_requires_confirmation(data, custom_profiles)


def _profile_source_ids(sources: object) -> list[str]:
    """Safely reduce optional custom-profile source metadata for a flow preview."""
    if not isinstance(sources, Sequence) or isinstance(sources, str | bytes):
        return []
    return [
        str(source["id"])
        for source in sources
        if isinstance(source, Mapping) and source.get("id") is not None
    ]


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
    if user_input.get(CONF_AUTOMATION_ENABLED) and not user_input.get(
        CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED, False
    ):
        return "hardware_shutoff_acknowledgement_required"
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


def _choice(options: list[str], translation_key: str) -> SelectSelector:
    """Return a translated single-choice selector."""
    return SelectSelector(SelectSelectorConfig(options=options, translation_key=translation_key))


def _installation_purpose_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): TextSelector(),
            vol.Required("purpose", default="private_garden"): _choice(
                ["private_garden", "landscape", "food_garden", "mixed"], "installation_purpose"
            ),
        }
    )


def _installation_hardware_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Optional(CONF_MAIN_VALVE): EntitySelector(
                EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
            ),
            vol.Optional(CONF_MAIN_VALVE_FEEDBACK): EntitySelector(
                EntitySelectorConfig(
                    domain=[Platform.BINARY_SENSOR, Platform.SWITCH, Platform.VALVE]
                )
            ),
        }
    )


def _installation_meter_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("meter_kind", default="none"): _choice(
                ["cumulative", "raw", "none"], "meter_kind"
            ),
            vol.Optional(CONF_WATER_METER): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR)
            ),
            vol.Optional(CONF_RAW_METER): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR)
            ),
            vol.Optional(CONF_LITERS_PER_COUNT): NumberSelector(
                NumberSelectorConfig(
                    min=0.001, max=1_000_000, step=0.001, mode=NumberSelectorMode.BOX
                )
            ),
            vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR)
            ),
        }
    )


def _installation_weather_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("weather_strategy", default="recommended"): _choice(
                ["recommended", "local", "open_meteo", "seasonal"], "weather_strategy"
            ),
            vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
                EntitySelectorConfig(domain=Platform.WEATHER)
            ),
            vol.Optional(CONF_ET0_SENSORS, default=[]): EntitySelector(
                EntitySelectorConfig(domain=Platform.SENSOR, multiple=True)
            ),
        }
    )


def _installation_safety_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_INSTALLATION_MAX_DELIVERY_RUNTIME, default=14_400): NumberSelector(
                NumberSelectorConfig(
                    min=60,
                    max=604_800,
                    step=60,
                    mode=NumberSelectorMode.BOX,
                    unit_of_measurement=UnitOfTime.SECONDS,
                )
            ),
            vol.Required(CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED, default=False): BooleanSelector(),
        }
    )


_PLANT_BY_CATEGORY = {
    "raised_bed": "builtin:plant:mixed-vegetables:v1",
    "vegetables": "builtin:plant:mixed-vegetables:v1",
    "lawn": "builtin:plant:cool-season-turf:v1",
    "shrubs": "builtin:plant:established-shrubs-hedges:v1",
    "flowers": "builtin:plant:groundcover-perennials:v1",
    "young_tree": "builtin:plant:young-fruit-tree:v1",
}
_SOIL_BY_ANSWER = {
    "unknown": "builtin:soil:sand:v1",
    "potting_mix": "builtin:soil:loam:v1",
    "mineral_mix": "builtin:soil:sandy-loam:v1",
    "sand": "builtin:soil:sand:v1",
    "sandy_loam": "builtin:soil:sandy-loam:v1",
    "loam": "builtin:soil:loam:v1",
    "clay_loam": "builtin:soil:clay-loam:v1",
    "clay": "builtin:soil:clay:v1",
}
_IRRIGATION_BY_METHOD = {
    "drip": "builtin:irrigation:drip:v1",
    "microspray": "builtin:irrigation:microspray:v1",
    "fixed_spray": "builtin:irrigation:fixed-spray:v1",
    "rotor": "builtin:irrigation:rotor:v1",
}

_PROFILE_OVERRIDE_KEYS = {
    CONF_PLANT_PROFILE: {
        "total_available_water_mm",
        "readily_available_water_mm",
        CONF_MAXIMUM_DEFICIT_MM,
        "effective_root_depth_m",
        "depletion_fraction",
        CONF_CROP_FACTOR,
        CONF_SEASONAL_CROP_FACTORS,
        "seasonal_kc",
        "seasonal_plant_factor",
        "coefficient_basis",
    },
    CONF_SOIL_PROFILE: {
        "total_available_water_mm",
        "readily_available_water_mm",
        CONF_MAXIMUM_DEFICIT_MM,
        "available_water_capacity_mm_m",
        "infiltration_ceiling_mm_h",
    },
    CONF_IRRIGATION_PROFILE: {CONF_APPLICATION_EFFICIENCY},
    CONF_EXPOSURE_PROFILE: {"location_factor", CONF_RAIN_FACTOR},
}


def _clear_stale_profile_overrides(
    data: dict[str, Any], previous_profiles: Mapping[str, object]
) -> None:
    """Remove only overrides invalidated by a changed inherited profile."""
    changed = {
        profile_key
        for profile_key in _PROFILE_OVERRIDE_KEYS
        if previous_profiles.get(profile_key) != data.get(profile_key)
    }
    if not changed:
        return
    top_level_stale = {
        CONF_PLANT_PROFILE: {
            CONF_CROP_FACTOR,
            CONF_SEASONAL_CROP_FACTORS,
            CONF_PHENOLOGY_STAGE_SCHEDULE,
        },
        CONF_SOIL_PROFILE: {CONF_MAXIMUM_DEFICIT_MM},
        CONF_IRRIGATION_PROFILE: {CONF_APPLICATION_EFFICIENCY},
        CONF_EXPOSURE_PROFILE: {CONF_RAIN_FACTOR},
    }
    for key in set().union(*(top_level_stale[profile] for profile in changed)):
        data.pop(key, None)
    stale_keys = set().union(*(_PROFILE_OVERRIDE_KEYS[key] for key in changed))
    overrides = data.get(CONF_PROFILE_OVERRIDES)
    if isinstance(overrides, Mapping):
        data[CONF_PROFILE_OVERRIDES] = {
            key: value for key, value in overrides.items() if key not in stale_keys
        }
    subareas = data.get(CONF_SUBAREAS)
    if not isinstance(subareas, list):
        return
    cleaned_subareas: list[object] = []
    for raw_subarea in subareas:
        if not isinstance(raw_subarea, Mapping):
            cleaned_subareas.append(raw_subarea)
            continue
        inherited_changes = {key for key in changed if key not in raw_subarea}
        inherited_stale = set().union(*(_PROFILE_OVERRIDE_KEYS[key] for key in inherited_changes))
        subarea_overrides = raw_subarea.get("overrides")
        cleaned_subareas.append(
            {
                **raw_subarea,
                **(
                    {
                        "overrides": {
                            key: value
                            for key, value in subarea_overrides.items()
                            if key not in inherited_stale
                        }
                    }
                    if isinstance(subarea_overrides, Mapping)
                    else {}
                ),
            }
        )
    data[CONF_SUBAREAS] = cleaned_subareas


def _catalog_profile_values(profile_id: str) -> Mapping[str, object]:
    profile = BUILTIN_PROFILES.get(profile_id, {})
    values = profile.get("values", {})
    return cast(Mapping[str, object], values) if isinstance(values, Mapping) else {}


def _apply_raised_bed_storage(zone: dict[str, Any], usable_depth_cm: float) -> None:
    """Clamp researched root-zone storage to the usable raised-bed depth."""
    plant = _catalog_profile_values(str(zone[CONF_PLANT_PROFILE]))
    soil = _catalog_profile_values(str(zone[CONF_SOIL_PROFILE]))
    stages = plant.get("phenology_stages")
    root_depth = plant.get("effective_root_depth_m")
    if isinstance(stages, Mapping):
        stage = stages.get(str(plant.get("conservative_stage", "mid")))
        if isinstance(stage, Mapping):
            root_depth = stage.get("effective_root_depth_m")
    awc = soil.get("available_water_capacity_mm_m")
    depletion = plant.get("depletion_fraction")
    if all(isinstance(value, int | float) for value in (root_depth, awc, depletion)):
        effective_depth = min(float(cast(float, root_depth)), usable_depth_cm / 100)
        taw = float(cast(float, awc)) * effective_depth
        zone[CONF_PROFILE_OVERRIDES] = {
            **cast(dict[str, Any], zone.get(CONF_PROFILE_OVERRIDES, {})),
            "total_available_water_mm": round(taw, 2),
            "readily_available_water_mm": round(taw * float(cast(float, depletion)), 2),
        }


def _plain_profile_preview(
    data: Mapping[str, Any], custom_profiles: object, language: str, flow_lpm: float | None
) -> str:
    """Describe recommendations and derived quantities without exposing raw objects."""
    summary = profile_selection_summary(data, custom_profiles, dt_util.now().date(), language)
    effective = resolve_effective_zone_profile(data, custom_profiles, dt_util.now().date())
    gross_per_mm = float(cast(float, effective.resolved_inputs["gross_liters_per_zone_deficit_mm"]))
    raw = effective.readily_available_water_mm
    liters = raw * gross_per_mm
    runtime = liters / flow_lpm if flow_lpm and flow_lpm > 0 else None
    names = ", ".join(
        str(item["name"]) for item in cast(list[dict[str, object]], summary["profiles"])
    )
    details = []
    for item in cast(list[dict[str, object]], summary["profiles"]):
        ranges = item.get("ranges")
        assumptions = item.get("assumptions")
        range_text = (
            ", ".join(f"{key}: {value}" for key, value in ranges.items())
            if isinstance(ranges, Mapping) and ranges
            else "fixed legacy value"
        )
        assumption_text = (
            " ".join(str(value) for value in assumptions)
            if isinstance(assumptions, Sequence) and not isinstance(assumptions, str | bytes)
            else ""
        )
        details.append(f"{item['name']} ({range_text}). {assumption_text}".strip())
    detail_text = " ".join(details)
    if language == "de":
        runtime_text = f"ca. {runtime:.0f} min" if runtime is not None else "nach Kalibrierung"
        return (
            f"Empfehlung aus Pflanzen-, Boden- und Hardwareangaben: {names}. "
            f"Bereiche und Annahmen: {detail_text} Nutzbarer Wasserspeicher: "
            f"{effective.total_available_water_mm:.1f} mm; Wasser vor Pflanzenstress: "
            f"{raw:.1f} mm. Erwartete Gabe: ca. {liters:.0f} l, Laufzeit {runtime_text}. "
            "Expertenbegriffe: TAW = nutzbarer Wasserspeicher, RAW = Wasser vor Stress. "
            "Die Werte sind Planungsannahmen innerhalb der angezeigten Profilbereiche."
        )
    runtime_text = f"about {runtime:.0f} min" if runtime is not None else "after calibration"
    return (
        f"Recommendation from the plant, soil, and hardware answers: {names}. "
        f"Ranges and assumptions: {detail_text} Usable water storage: "
        f"{effective.total_available_water_mm:.1f} mm; water available before plant stress: "
        f"{raw:.1f} mm. Expected dose: about {liters:.0f} L, runtime {runtime_text}. "
        "Expert terms: TAW = usable storage, RAW = water before stress. Values are planning "
        "assumptions within the displayed profile ranges."
    )


class IrrigationManagerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create and reconfigure irrigation installations."""

    VERSION = 1
    MINOR_VERSION = 7

    def __init__(self) -> None:
        """Initialize transient portable-import data."""
        self._pending_import_installation: dict[str, Any] | None = None
        self._pending_import_zones: list[dict[str, Any]] = []
        self._import_preview = ""
        self._import_profile_preview = ""
        self._import_profile_confirmation_required = False
        self._import_profile_confirmation_zone_indexes: set[int] = set()
        self._guided_installation: dict[str, Any] = {}
        self._guided_installation_preview = ""

    @override
    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the installation and zone expert settings flow."""
        return IrrigationManagerOptionsFlow()

    @override
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Choose whether to create or import an irrigation installation."""
        return self.async_show_menu(
            step_id="user", menu_options=["create", "expert_create", "import"]
        )

    async def async_step_create(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start a progressive plain-language installation setup."""
        if user_input is not None:
            self._guided_installation = {CONF_NAME: user_input[CONF_NAME]}
            return await self.async_step_installation_hardware()

        return self.async_show_form(step_id="create", data_schema=_installation_purpose_schema())

    async def async_step_expert_create(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retain direct access to the complete stored installation model."""
        if user_input is not None:
            if error := _validate_installation_input(user_input):
                return self.async_show_form(
                    step_id="expert_create", data_schema=INSTALLATION_SCHEMA, errors={"base": error}
                )
            await self.async_set_unique_id(uuid4().hex)
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        return self.async_show_form(step_id="expert_create", data_schema=INSTALLATION_SCHEMA)

    async def async_step_installation_hardware(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select the optional shared shutoff and independent feedback."""
        if user_input is not None:
            if user_input.get(CONF_MAIN_VALVE_FEEDBACK) and not user_input.get(CONF_MAIN_VALVE):
                return self.async_show_form(
                    step_id="installation_hardware",
                    data_schema=_installation_hardware_schema(),
                    errors={"base": "main_feedback_requires_main_valve"},
                )
            self._guided_installation.update(user_input)
            return await self.async_step_installation_meter()
        return self.async_show_form(
            step_id="installation_hardware", data_schema=_installation_hardware_schema()
        )

    async def async_step_installation_meter(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect only fields relevant to the selected meter capability."""
        if user_input is not None:
            kind = str(user_input.pop("meter_kind"))
            cumulative = user_input.get(CONF_WATER_METER)
            raw = user_input.get(CONF_RAW_METER)
            factor = user_input.get(CONF_LITERS_PER_COUNT)
            if (kind == "cumulative" and not cumulative) or (kind == "raw" and not raw):
                return self.async_show_form(
                    step_id="installation_meter",
                    data_schema=self.add_suggested_values_to_schema(
                        _installation_meter_schema(), {**user_input, "meter_kind": kind}
                    ),
                    errors={"base": "selected_meter_required"},
                )
            if kind == "raw" and not factor:
                return self.async_show_form(
                    step_id="installation_meter",
                    data_schema=self.add_suggested_values_to_schema(
                        _installation_meter_schema(), {**user_input, "meter_kind": kind}
                    ),
                    errors={"base": "raw_meter_requires_factor"},
                )
            for key in (CONF_WATER_METER, CONF_RAW_METER, CONF_LITERS_PER_COUNT):
                self._guided_installation.pop(key, None)
            if kind != "none":
                self._guided_installation.update(
                    {
                        key: value
                        for key, value in user_input.items()
                        if value not in (None, "", [])
                        and (key != CONF_WATER_METER or kind == "cumulative")
                        and (key not in (CONF_RAW_METER, CONF_LITERS_PER_COUNT) or kind == "raw")
                    }
                )
            elif user_input.get(CONF_FLOW_SENSOR):
                self._guided_installation[CONF_FLOW_SENSOR] = user_input[CONF_FLOW_SENSOR]
            self._guided_installation_preview = self._meter_capability_preview(kind, user_input)
            return await self.async_step_installation_weather()
        return self.async_show_form(
            step_id="installation_meter", data_schema=_installation_meter_schema()
        )

    def _meter_capability_preview(self, kind: str, data: Mapping[str, Any]) -> str:
        entity_id = data.get(CONF_WATER_METER) or data.get(CONF_RAW_METER)
        state = self.hass.states.get(str(entity_id)) if entity_id else None
        unit = state.attributes.get("unit_of_measurement") if state else None
        device_class = state.attributes.get("device_class") if state else None
        if self.hass.config.language == "de":
            return (
                f"Erkannt: {device_class or 'unbekannte Geräteklasse'}, Einheit "
                f"{unit or 'nicht angegeben'}. "
                + (
                    "Mengensteuerung und gemessene Verbrauchswerte sind möglich."
                    if kind != "none"
                    else "Ohne Zähler ist nur geschätzte Zeitsteuerung möglich."
                )
            )
        return (
            f"Detected: {device_class or 'unknown device class'}, unit {unit or 'not reported'}. "
            + (
                "Volume control and measured consumption are available."
                if kind != "none"
                else "Without a meter, only estimated time control is available."
            )
        )

    async def async_step_installation_weather(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Recommend a weather source while allowing an explicit alternative."""
        if user_input is not None:
            strategy = str(user_input.pop("weather_strategy"))
            if strategy == "local" and not (
                user_input.get(CONF_WEATHER_ENTITY) or user_input.get(CONF_ET0_SENSORS)
            ):
                return self.async_show_form(
                    step_id="installation_weather",
                    data_schema=self.add_suggested_values_to_schema(
                        _installation_weather_schema(), {**user_input, "weather_strategy": strategy}
                    ),
                    errors={"base": "local_weather_source_required"},
                    description_placeholders={
                        "meter_preview": self._guided_installation_preview,
                        "comparison": self._weather_comparison(),
                    },
                )
            self._guided_installation.update(
                {key: value for key, value in user_input.items() if value not in (None, "", [])}
            )
            has_local = bool(
                user_input.get(CONF_WEATHER_ENTITY) or user_input.get(CONF_ET0_SENSORS)
            )
            self._guided_installation[CONF_OPEN_METEO_ENABLED] = strategy == "open_meteo" or (
                strategy == "recommended" and not has_local
            )
            return await self.async_step_installation_safety()
        return self.async_show_form(
            step_id="installation_weather",
            data_schema=_installation_weather_schema(),
            description_placeholders={
                "meter_preview": self._guided_installation_preview,
                "comparison": self._weather_comparison(),
            },
        )

    def _weather_comparison(self) -> str:
        """Summarize source tradeoffs and the recommendation from current availability."""
        local_count = len(self.hass.states.async_entity_ids(Platform.WEATHER))
        if self.hass.config.language == "de":
            recommendation = (
                "Prüfe zuerst eine vorhandene lokale Wetter-Entity."
                if local_count
                else "Open-Meteo ist die empfohlene sofort verfügbare Quelle."
            )
            return (
                f"Vergleich: {local_count} lokale Wetter-Entities erkannt; lokale Quellen können "
                "Standortmessungen liefern, Open-Meteo liefert eine konsistente externe Prognose, "
                f"saisonale Werte reagieren nicht auf aktuelles Wetter. {recommendation}"
            )
        recommendation = (
            "Review an available local weather entity first."
            if local_count
            else "Open-Meteo is the recommended immediately available source."
        )
        return (
            f"Comparison: {local_count} local weather entities detected; local sources may provide "
            "site observations, Open-Meteo provides a consistent external forecast, and seasonal "
            f"values do not react to current weather. {recommendation}"
        )

    async def async_step_installation_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require acknowledgment that software is not the final physical shutoff."""
        if user_input is not None:
            if user_input.get(CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED) is not True:
                return self.async_show_form(
                    step_id="installation_safety",
                    data_schema=self.add_suggested_values_to_schema(
                        _installation_safety_schema(), user_input
                    ),
                    errors={"base": "hardware_shutoff_acknowledgement_required"},
                )
            self._guided_installation.update(user_input)
            return await self.async_step_installation_review()
        return self.async_show_form(
            step_id="installation_safety", data_schema=_installation_safety_schema()
        )

    async def async_step_installation_review(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show dry-run readiness before creating an installation."""
        normalized = dict(INSTALLATION_SCHEMA(self._guided_installation))
        if user_input is not None:
            if user_input.get("confirm_ready") is not True:
                return await self.async_step_installation_safety()
            if error := _validate_installation_input(normalized):
                return self.async_abort(reason=error)
            await self.async_set_unique_id(uuid4().hex)
            return self.async_create_entry(title=str(normalized[CONF_NAME]), data=normalized)
        meter = (
            "configured"
            if normalized.get(CONF_WATER_METER) or normalized.get(CONF_RAW_METER)
            else "none"
        )
        weather = "Open-Meteo" if normalized.get(CONF_OPEN_METEO_ENABLED) else "local/seasonal"
        if self.hass.config.language == "de":
            meter = "konfiguriert" if meter == "configured" else "keiner"
            weather = "lokal/saisonal" if weather == "local/seasonal" else weather
            preview = (
                f"{normalized[CONF_NAME]} | Zähler: {meter} | Wetter: {weather} | "
                "Hardware-Abschalthinweis bestätigt | bereit für Zoneneinrichtung und "
                "Trockenlauf; automatische Zonen bleiben bis Profilbestätigung und "
                "Durchflusskalibrierung gesperrt."
            )
        else:
            preview = (
                f"{normalized[CONF_NAME]} | meter: {meter} | weather: {weather} | "
                "hardware shutoff warning accepted | ready for zone setup and dry-run; "
                "automatic zones remain blocked until profile confirmation and flow calibration."
            )
        return self.async_show_form(
            step_id="installation_review",
            data_schema=vol.Schema(
                {vol.Required("confirm_ready", default=False): BooleanSelector()}
            ),
            description_placeholders={"preview": preview},
        )

    async def async_step_import(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Validate a portable export before creating a new installation atomically."""
        if user_input is None:
            return self.async_show_form(
                step_id="import",
                data_schema=vol.Schema(
                    {
                        vol.Required("payload"): ObjectSelector(),
                        vol.Optional("entity_remapping", default={}): ObjectSelector(),
                    }
                ),
            )
        try:
            installation, zones = self._validate_new_entry_import(user_input)
        except TypeError, ValueError, vol.Invalid:
            return self.async_abort(reason="invalid_import")
        if self._import_ownership_conflicts(installation, zones):
            return self.async_abort(reason="actuator_already_owned")
        self._pending_import_installation = installation
        self._pending_import_zones = zones
        self._import_preview = json.dumps(
            {
                "installation": installation[CONF_NAME],
                "zones": [zone[CONF_NAME] for zone in zones],
                "fresh_unique_ids": True,
            },
            sort_keys=True,
        )
        if self._import_profile_confirmation_required:
            return await self.async_step_import_profile_confirmation()
        return await self.async_step_import_confirm()

    async def async_step_import_profile_confirmation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require local confirmation instead of trusting imported agronomic flags."""
        if self._pending_import_installation is None:
            return self.async_abort(reason="import_not_pending")
        if user_input is None:
            return self.async_show_form(
                step_id="import_profile_confirmation",
                data_schema=vol.Schema(
                    {vol.Required("confirm_researched_profiles", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": self._import_profile_preview},
            )
        if user_input.get("confirm_researched_profiles") is not True:
            return self.async_abort(reason="profile_selection_cancelled")
        self._pending_import_zones = [
            {
                **zone,
                CONF_AGRONOMIC_VALUES_CONFIRMED: True,
            }
            if index in self._import_profile_confirmation_zone_indexes
            else zone
            for index, zone in enumerate(self._pending_import_zones)
        ]
        return await self.async_step_import_confirm()

    async def async_step_import_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create one entry and all imported zones after explicit confirmation."""
        installation = self._pending_import_installation
        if installation is None:
            return self.async_abort(reason="import_not_pending")
        if user_input is None:
            return self.async_show_form(
                step_id="import_confirm",
                data_schema=vol.Schema(
                    {vol.Required("confirm_create", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": self._import_preview},
            )
        if user_input.get("confirm_create") is not True:
            return self.async_abort(reason="import_cancelled")
        zones = self._pending_import_zones
        async with _IMPORT_CREATE_LOCK:
            if self._import_ownership_conflicts(installation, zones):
                return self.async_abort(reason="actuator_already_owned")
            await self.async_set_unique_id(uuid4().hex)
            # HA validates and commits this entry plus every subentry atomically.
            result = self.async_create_entry(
                title=str(installation[CONF_NAME]),
                data=installation,
                subentries=[
                    ConfigSubentryData(
                        data=zone,
                        subentry_type=SUBENTRY_TYPE_ZONE,
                        title=str(zone[CONF_NAME]),
                        unique_id=uuid4().hex,
                    )
                    for zone in zones
                ],
            )
        self._pending_import_installation = None
        self._pending_import_zones = []
        self._import_profile_confirmation_zone_indexes.clear()
        return result

    def _validate_new_entry_import(
        self,
        user_input: Mapping[str, object],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Return schema-normalized installation and zone data from a portable export."""
        payload = user_input.get("payload")
        entity_remapping = user_input.get("entity_remapping", {})
        if (
            not isinstance(payload, Mapping)
            or payload.get("integration") != DOMAIN
            or payload.get("schema_version") != EXPORT_SCHEMA_VERSION
            or not isinstance(payload.get("profile_catalog_version", 1), int)
            or cast(int, payload.get("profile_catalog_version", 1)) > PROFILE_CATALOG_VERSION
            or not isinstance(entity_remapping, Mapping)
            or not all(
                isinstance(source, str) and isinstance(target, str)
                for source, target in entity_remapping.items()
            )
        ):
            raise ValueError("Invalid portable import envelope")
        raw_installation = payload.get("installation")
        raw_zones = payload.get("zones")
        if (
            not isinstance(raw_installation, Mapping)
            or not isinstance(raw_installation.get("config"), Mapping)
            or not isinstance(raw_zones, list)
            or not raw_zones
        ):
            raise ValueError("Portable import requires an installation and zones")
        remapping = cast(Mapping[str, str], entity_remapping)
        legacy_installation = IrrigationManager._remap_import_entities(
            dict(cast(Mapping[str, object], raw_installation["config"])), remapping
        )
        # Imported acknowledgement is never trusted; it must be made locally.
        legacy_installation[CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED] = False
        legacy_installation[CONF_AUTOMATION_ENABLED] = False
        installation = dict(INSTALLATION_SCHEMA(legacy_installation))
        if error := _validate_installation_input(installation):
            raise ValueError(error)
        zones: list[dict[str, Any]] = []
        researched_summaries: list[dict[str, object]] = []
        self._import_profile_confirmation_zone_indexes.clear()
        source_ids: set[str] = set()
        valves: set[str] = set()
        for raw_zone in raw_zones:
            if (
                not isinstance(raw_zone, Mapping)
                or not isinstance(raw_zone.get("id"), str)
                or raw_zone["id"] in source_ids
                or not isinstance(raw_zone.get("config"), Mapping)
            ):
                raise ValueError("Malformed or duplicate portable zone")
            source_ids.add(cast(str, raw_zone["id"]))
            zone = dict(
                ZONE_SCHEMA(
                    IrrigationManager._remap_import_entities(
                        dict(cast(Mapping[str, object], raw_zone["config"])), remapping
                    )
                )
            )
            zone[CONF_AUTOMATION_ENABLED] = False
            custom_profiles = installation.get(CONF_CUSTOM_PROFILES, {})
            imported_confirmation = zone.get(CONF_AGRONOMIC_VALUES_CONFIRMED) is True
            requires_confirmation = selection_requires_confirmation(zone, custom_profiles)
            requires_local_confirmation = requires_confirmation or imported_confirmation
            validation_zone = (
                {**zone, CONF_AGRONOMIC_VALUES_CONFIRMED: True}
                if requires_local_confirmation
                else zone
            )
            if error := _validate_zone_input(validation_zone, custom_profiles):
                raise ValueError(error)
            zone[CONF_AGRONOMIC_VALUES_CONFIRMED] = False
            if requires_local_confirmation:
                self._import_profile_confirmation_zone_indexes.add(len(zones))
                researched_summaries.append(
                    {
                        "zone": zone[CONF_NAME],
                        "profiles": profile_selection_summary(
                            zone, custom_profiles, dt_util.now().date(), self.hass.config.language
                        ),
                    }
                )
            valve = cast(str, zone[CONF_ZONE_VALVE])
            if valve in valves:
                raise ValueError("Portable zones cannot share a valve")
            valves.add(valve)
            zones.append(zone)
        self._import_profile_confirmation_required = bool(researched_summaries)
        self._import_profile_preview = json.dumps(
            researched_summaries, ensure_ascii=True, sort_keys=True
        )
        imported_entity_ids = IrrigationManager._import_entity_ids(
            installation,
            [{"config": zone} for zone in zones],
        )
        if any(self.hass.states.get(entity_id) is None for entity_id in imported_entity_ids):
            raise ValueError("Portable import references unavailable target entities")
        candidate_ownership = self._import_owned_entities(installation, zones)
        if len(candidate_ownership) != sum(
            1
            for data in (installation, *zones)
            for key in (
                (CONF_MAIN_VALVE, CONF_MAIN_VALVE_FEEDBACK)
                if data is installation
                else (CONF_ZONE_VALVE, CONF_ZONE_VALVE_FEEDBACK)
            )
            if isinstance(data.get(key), str)
        ):
            raise ValueError("Portable import assigns one actuator or feedback more than once")
        return installation, zones

    def _import_ownership_conflicts(
        self,
        installation: Mapping[str, object],
        zones: list[dict[str, Any]],
    ) -> bool:
        """Return whether any existing installation already owns an imported endpoint."""
        candidate = self._import_owned_entities(installation, zones)
        existing: set[str] = set()
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            existing.update(self._import_owned_entities(entry.data, []))
            existing.update(
                entity_id
                for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
                for key in (CONF_ZONE_VALVE, CONF_ZONE_VALVE_FEEDBACK)
                if isinstance((entity_id := subentry.data.get(key)), str)
            )
        return not candidate.isdisjoint(existing)

    @staticmethod
    def _import_owned_entities(
        installation: Mapping[str, object],
        zones: list[dict[str, Any]],
    ) -> set[str]:
        """Collect actuators and feedback entities exclusively owned by one import."""
        owned = {
            entity_id
            for key in (CONF_MAIN_VALVE, CONF_MAIN_VALVE_FEEDBACK)
            if isinstance((entity_id := installation.get(key)), str)
        }
        owned.update(
            entity_id
            for zone in zones
            for key in (CONF_ZONE_VALVE, CONF_ZONE_VALVE_FEEDBACK)
            if isinstance((entity_id := zone.get(key)), str)
        )
        return owned

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

    def __init__(self) -> None:
        """Initialize the explicit researched-profile confirmation state."""
        self._pending_zone_input: dict[str, Any] | None = None
        self._pending_reconfigure = False
        self._profile_preview = ""
        self._guided_zone: dict[str, Any] = {}
        self._guided_answers: dict[str, Any] = {}
        self._guided_flow_lpm: float | None = None
        self._calibration_test_id: str | None = None
        self._calibration_previous_proposal_id: str | None = None
        self._calibration_proposal: dict[str, object] | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Choose guided setup or the complete expert form."""
        if user_input is not None:
            if user_input["setup_mode"] == "expert":
                return await self.async_step_expert()
            self._guided_zone = {}
            self._guided_answers = {}
            self._pending_reconfigure = False
            return await self.async_step_zone_basic()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_mode", default="guided"): _choice(
                        ["guided", "expert"], "setup_mode"
                    )
                }
            ),
        )

    async def async_step_expert(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Add a zone through the complete persisted model."""
        if user_input is not None:
            if error := _validate_zone_input(
                user_input, self._get_entry().data.get(CONF_CUSTOM_PROFILES, {})
            ):
                return self.async_show_form(
                    step_id="expert",
                    data_schema=_zone_schema(
                        self._get_entry().data.get(CONF_CUSTOM_PROFILES, {}),
                        self.hass.config.language,
                    ),
                    errors={"base": error},
                )
            if self._valve_is_configured(user_input[CONF_ZONE_VALVE]):
                return self.async_abort(reason="already_configured")
            preview, required = _profile_preview(
                user_input,
                self._get_entry().data.get(CONF_CUSTOM_PROFILES, {}),
                self.hass.config.language,
            )
            if required:
                self._pending_zone_input = user_input
                self._pending_reconfigure = False
                self._profile_preview = preview
                return await self.async_step_profile_confirmation()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
                unique_id=uuid4().hex,
            )

        return self.async_show_form(
            step_id="expert",
            data_schema=_zone_schema(
                self._get_entry().data.get(CONF_CUSTOM_PROFILES, {}), self.hass.config.language
            ),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose zone configuration or a supervised calibration."""
        return self.async_show_menu(
            step_id="reconfigure",
            menu_options=["reconfigure_guided", "reconfigure_expert", "calibration"],
        )

    async def async_step_reconfigure_guided(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start the guided editor for this existing zone."""
        self._guided_zone = dict(self._get_reconfigure_subentry().data)
        self._guided_answers = {}
        self._pending_reconfigure = True
        return await self.async_step_zone_basic()

    def _manager(self) -> IrrigationManager | None:
        """Return the loaded runtime owned by this zone's installation."""
        runtime = self.hass.data.get(DOMAIN, {}).get(self._get_entry().entry_id)
        return cast(IrrigationManager, runtime) if runtime is not None else None

    def _calibration_duration_limit(self) -> float:
        """Keep the guided measurement inside both hard and dead-man deadlines."""
        data = self._get_entry().data
        hard_limit = float(data.get(CONF_MAINTENANCE_MAX_DURATION, 300.0))
        confirmation = float(data.get(CONF_MAINTENANCE_CONFIRMATION_INTERVAL, 30.0))
        settle = float(data.get(CONF_CALIBRATION_SETTLE_SECONDS, 2.0))
        return min(20.0, min(hard_limit, confirmation) - settle - 2.0)

    async def async_step_calibration(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start one short, supervised flow measurement for this zone."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        duration_limit = self._calibration_duration_limit()
        if duration_limit < 1:
            return self.async_abort(reason="calibration_configuration_invalid")
        schema = vol.Schema(
            {
                vol.Required("duration", default=min(20.0, duration_limit)): NumberSelector(
                    NumberSelectorConfig(
                        min=1,
                        max=duration_limit,
                        step=1,
                        mode=NumberSelectorMode.BOX,
                        unit_of_measurement=UnitOfTime.SECONDS,
                    )
                ),
                vol.Required("confirm_supervision", default=False): BooleanSelector(),
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="calibration",
                data_schema=schema,
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        if user_input.get("confirm_supervision") is not True:
            return self.async_show_form(
                step_id="calibration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_supervision_required"},
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        previous = manager.calibration_proposal()
        self._calibration_previous_proposal_id = (
            str(previous["proposal_id"]) if previous is not None else None
        )
        try:
            started = await manager.async_start_maintenance_test(
                zone_subentry_id=self._get_reconfigure_subentry().subentry_id,
                duration_seconds=float(user_input["duration"]),
                kind="calibration",
            )
        except HomeAssistantError:
            return self.async_show_form(
                step_id="calibration",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_start_failed"},
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        self._calibration_test_id = str(started["test_id"])
        return await self.async_step_calibration_running()

    async def async_step_calibration_running(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Let the operator refresh the bounded measurement and renew its supervision."""
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        test_id = self._calibration_test_id
        if test_id is None:
            return self.async_abort(reason="calibration_not_started")
        if user_input is None:
            return self.async_show_form(
                step_id="calibration_running",
                data_schema=vol.Schema({}),
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        if manager.is_supervised_test_active(test_id):
            await manager.async_confirm_maintenance_test(test_id=test_id)
            return self.async_show_form(
                step_id="calibration_running",
                data_schema=vol.Schema({}),
                errors={"base": "calibration_still_running"},
                description_placeholders={"zone": self._get_reconfigure_subentry().title},
            )
        proposal = manager.calibration_proposal()
        if (
            proposal is None
            or proposal.get("proposal_id") == self._calibration_previous_proposal_id
            or proposal.get("zone_subentry_id") != self._get_reconfigure_subentry().subentry_id
            or proposal.get("status") != "pending"
        ):
            return self.async_abort(reason="calibration_no_proposal")
        self._calibration_proposal = proposal
        return await self.async_step_calibration_review()

    def _calibration_preview(self) -> str:
        """Render the measured proposal in the configured UI language."""
        proposal = self._calibration_proposal or {}

        def number(key: str) -> float:
            value = proposal.get(key)
            return float(value) if isinstance(value, int | float) else 0.0

        average = number("average_flow_l_min")
        minimum = number("proposed_min_flow_l_min")
        maximum = number("proposed_max_flow_l_min")
        liters = number("delivered_liters")
        duration = number("duration_seconds")
        latency = number("opening_latency_seconds")
        post_run = number("post_run_liters")
        if self.hass.config.language == "de":
            return (
                f"Gemittelt {average:.1f} l/min aus {liters:.1f} l in {duration:.1f} s. "
                f"Vorgeschlagener Normalbereich: {minimum:.1f}-{maximum:.1f} l/min. "
                f"Ventilöffnung: {latency:.1f} s; Nachlauf: {post_run:.1f} l."
            )
        return (
            f"Average {average:.1f} L/min from {liters:.1f} L in {duration:.1f} s. "
            f"Proposed normal range: {minimum:.1f}-{maximum:.1f} L/min. "
            f"Valve opening: {latency:.1f} s; post-run: {post_run:.1f} L."
        )

    async def async_step_calibration_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Apply or discard measured flow limits only after explicit review."""
        proposal = self._calibration_proposal
        manager = self._manager()
        if proposal is None:
            return self.async_abort(reason="calibration_no_proposal")
        if manager is None:
            return self.async_abort(reason="installation_not_loaded")
        schema = vol.Schema(
            {
                vol.Required("resolution", default="discard"): _choice(
                    ["accept", "discard"], "calibration_resolution"
                ),
                vol.Required("confirm_resolution", default=False): BooleanSelector(),
            }
        )
        if user_input is None:
            return self.async_show_form(
                step_id="calibration_review",
                data_schema=schema,
                description_placeholders={"result": self._calibration_preview()},
            )
        if user_input.get("confirm_resolution") is not True:
            return self.async_show_form(
                step_id="calibration_review",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_resolution_required"},
                description_placeholders={"result": self._calibration_preview()},
            )
        resolution = str(user_input["resolution"])
        try:
            await manager.async_resolve_calibration(
                proposal_id=str(proposal["proposal_id"]), resolution=resolution
            )
        except HomeAssistantError:
            return self.async_show_form(
                step_id="calibration_review",
                data_schema=self.add_suggested_values_to_schema(schema, user_input),
                errors={"base": "calibration_resolution_failed"},
                description_placeholders={"result": self._calibration_preview()},
            )
        return self.async_abort(
            reason="calibration_accepted" if resolution == "accept" else "calibration_discarded"
        )

    async def async_step_reconfigure_expert(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Update every stored zone field without changing stable identity."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        if user_input is not None:
            if error := _validate_zone_input(user_input, entry.data.get(CONF_CUSTOM_PROFILES, {})):
                return self.async_show_form(
                    step_id="reconfigure_expert",
                    data_schema=self.add_suggested_values_to_schema(
                        _zone_schema(
                            entry.data.get(CONF_CUSTOM_PROFILES, {}), self.hass.config.language
                        ),
                        user_input,
                    ),
                    errors={"base": error},
                )
            if self._valve_is_configured(
                user_input[CONF_ZONE_VALVE],
                excluding_subentry_id=subentry.subentry_id,
            ):
                return self.async_abort(reason="already_configured")
            preview, required = _profile_preview(
                user_input,
                entry.data.get(CONF_CUSTOM_PROFILES, {}),
                self.hass.config.language,
            )
            if required:
                self._pending_zone_input = user_input
                self._pending_reconfigure = True
                self._profile_preview = preview
                return await self.async_step_profile_confirmation()
            return self.async_update_and_abort(
                entry,
                subentry,
                title=user_input[CONF_NAME],
                data=user_input,
            )

        return self.async_show_form(
            step_id="reconfigure_expert",
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema(entry.data.get(CONF_CUSTOM_PROFILES, {}), self.hass.config.language),
                subentry.data,
            ),
        )

    async def async_step_zone_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the physical valve and a recognizable zone category."""
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_ZONE_VALVE): EntitySelector(
                    EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
                ),
                vol.Optional(CONF_ZONE_VALVE_FEEDBACK): EntitySelector(
                    EntitySelectorConfig(
                        domain=[Platform.BINARY_SENSOR, Platform.SWITCH, Platform.VALVE]
                    )
                ),
                vol.Required("zone_category", default="raised_bed"): _choice(
                    ["raised_bed", "vegetables", "lawn", "shrubs", "flowers", "young_tree"],
                    "zone_category",
                ),
            }
        )
        if user_input is not None:
            if self._valve_is_configured(
                user_input[CONF_ZONE_VALVE],
                self._get_reconfigure_subentry().subentry_id if self._pending_reconfigure else None,
            ):
                return self.async_abort(reason="already_configured")
            category = str(user_input.pop("zone_category"))
            self._guided_zone.update(user_input)
            self._guided_answers["zone_category"] = category
            return await self.async_step_zone_area()
        suggested = self._guided_zone if self._guided_zone else None
        return self.async_show_form(
            step_id="zone_basic",
            data_schema=(
                self.add_suggested_values_to_schema(schema, suggested) if suggested else schema
            ),
        )

    async def async_step_zone_area(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Estimate area from a direct value or simple rectangle."""
        schema = vol.Schema(
            {
                vol.Required("area_method", default="measured"): _choice(
                    ["measured", "rectangle", "unknown"], "area_method"
                ),
                vol.Optional(CONF_AREA_M2): NumberSelector(
                    NumberSelectorConfig(
                        min=0.1, max=100_000, step=0.1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Optional("length_m"): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional("width_m"): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        if user_input is not None:
            method = str(user_input["area_method"])
            if method == "measured" and not user_input.get(CONF_AREA_M2):
                return self.async_show_form(
                    step_id="zone_area", data_schema=schema, errors={"base": "area_required"}
                )
            if method == "rectangle" and not all(
                user_input.get(key) for key in ("length_m", "width_m")
            ):
                return self.async_show_form(
                    step_id="zone_area", data_schema=schema, errors={"base": "dimensions_required"}
                )
            area = (
                float(user_input[CONF_AREA_M2])
                if method == "measured"
                else float(user_input["length_m"]) * float(user_input["width_m"])
                if method == "rectangle"
                else float(self._guided_zone.get(CONF_AREA_M2, 1.0))
            )
            self._guided_zone[CONF_AREA_M2] = round(area, 2)
            self._guided_answers["area_method"] = method
            if self._guided_answers["zone_category"] == "raised_bed":
                return await self.async_step_zone_raised_bed()
            return await self.async_step_zone_profiles()
        return self.async_show_form(step_id="zone_area", data_schema=schema)

    async def async_step_zone_raised_bed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Capture raised-bed depth and observable soil-mix properties."""
        schema = vol.Schema(
            {
                vol.Required("usable_depth_cm", default=35): NumberSelector(
                    NumberSelectorConfig(min=10, max=150, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required("soil_answer", default="unknown"): _choice(
                    [
                        "potting_mix",
                        "mineral_mix",
                        "sand",
                        "sandy_loam",
                        "loam",
                        "clay_loam",
                        "clay",
                        "unknown",
                    ],
                    "soil_answer",
                ),
                vol.Required("bed_age", default="established"): _choice(
                    ["new", "established", "unknown"], "bed_age"
                ),
                vol.Required("organic_rich", default="unknown"): _choice(
                    ["yes", "no", "unknown"], "answer_unknown"
                ),
                vol.Required("drainage", default="normal"): _choice(
                    ["fast", "normal", "slow", "unknown"], "drainage"
                ),
            }
        )
        if user_input is not None:
            self._guided_answers.update(user_input)
            self._guided_zone[CONF_SOIL_PROFILE] = _SOIL_BY_ANSWER[str(user_input["soil_answer"])]
            return await self.async_step_zone_profiles()
        return self.async_show_form(step_id="zone_raised_bed", data_schema=schema)

    async def async_step_zone_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Choose recognizable plants, irrigation hardware, soil, and exposure."""
        schema_fields: dict[object, object] = {
            vol.Required(
                "plant_choice",
                default=(
                    "vegetables"
                    if self._guided_answers["zone_category"] == "raised_bed"
                    else self._guided_answers["zone_category"]
                ),
            ): _choice(["vegetables", "lawn", "shrubs", "flowers", "young_tree"], "plant_choice"),
            vol.Required("irrigation_method", default="drip"): _choice(
                ["drip", "microspray", "fixed_spray", "rotor"], "irrigation_method"
            ),
            vol.Required("exposure", default="full_sun"): _choice(
                ["full_sun", "partial_sun", "shade", "sheltered", "rain_shadow"], "exposure"
            ),
        }
        if self._guided_answers["zone_category"] != "raised_bed":
            schema_fields[vol.Required("soil_answer", default="unknown")] = _choice(
                ["sand", "sandy_loam", "loam", "clay_loam", "clay", "unknown"],
                "soil_answer",
            )
        schema = vol.Schema(schema_fields)
        if user_input is not None:
            self._guided_answers.update(user_input)
            previous_profiles = {key: self._guided_zone.get(key) for key in _PROFILE_OVERRIDE_KEYS}
            self._guided_zone[CONF_PLANT_PROFILE] = _PLANT_BY_CATEGORY[
                str(user_input["plant_choice"])
            ]
            if "soil_answer" in user_input:
                self._guided_zone[CONF_SOIL_PROFILE] = _SOIL_BY_ANSWER[
                    str(user_input["soil_answer"])
                ]
            self._guided_zone[CONF_EXPOSURE_PROFILE] = "builtin:exposure:generic-neutral:v1"
            self._guided_zone[CONF_IRRIGATION_PROFILE] = _IRRIGATION_BY_METHOD[
                str(user_input["irrigation_method"])
            ]
            _clear_stale_profile_overrides(self._guided_zone, previous_profiles)
            # Catalog v1 has no sourced exposure factors; exposure remains descriptive.
            overrides = self._guided_zone.get(CONF_PROFILE_OVERRIDES)
            if isinstance(overrides, Mapping):
                self._guided_zone[CONF_PROFILE_OVERRIDES] = {
                    key: value
                    for key, value in overrides.items()
                    if key not in {"location_factor", CONF_RAIN_FACTOR}
                }
            self._guided_zone[CONF_RAIN_FACTOR] = 1.0
            if "usable_depth_cm" in self._guided_answers:
                _apply_raised_bed_storage(
                    self._guided_zone, float(self._guided_answers["usable_depth_cm"])
                )
            return await self.async_step_zone_rate()
        return self.async_show_form(step_id="zone_profiles", data_schema=schema)

    async def async_step_zone_rate(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Separate measured calibration from estimates used only in the preview."""
        schema = vol.Schema(
            {
                vol.Required("rate_source", default="unknown"): _choice(
                    ["measured", "estimated", "unknown"], "rate_source"
                ),
                vol.Optional(CONF_MIN_FLOW): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_MAX_FLOW): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional("application_rate_mm_h"): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=1_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        if user_input is not None:
            source = str(user_input["rate_source"])
            if source == "measured" and not all(
                isinstance(user_input.get(key), int | float)
                for key in (CONF_MIN_FLOW, CONF_MAX_FLOW)
            ):
                return self.async_show_form(
                    step_id="zone_rate",
                    data_schema=schema,
                    errors={"base": "measured_flow_required"},
                )
            if source == "measured" and float(user_input[CONF_MIN_FLOW]) >= float(
                user_input[CONF_MAX_FLOW]
            ):
                return self.async_show_form(
                    step_id="zone_rate", data_schema=schema, errors={"base": "invalid_flow_range"}
                )
            if source == "estimated" and not user_input.get("application_rate_mm_h"):
                return self.async_show_form(
                    step_id="zone_rate",
                    data_schema=schema,
                    errors={"base": "application_rate_required"},
                )
            self._guided_answers.update(user_input)
            if source == "measured":
                self._guided_zone[CONF_MIN_FLOW] = user_input[CONF_MIN_FLOW]
                self._guided_zone[CONF_MAX_FLOW] = user_input[CONF_MAX_FLOW]
                self._guided_flow_lpm = (
                    float(user_input[CONF_MIN_FLOW]) + float(user_input[CONF_MAX_FLOW])
                ) / 2
            elif source == "estimated":
                self._guided_zone.pop(CONF_MIN_FLOW, None)
                self._guided_zone.pop(CONF_MAX_FLOW, None)
                self._guided_flow_lpm = (
                    float(user_input["application_rate_mm_h"])
                    * float(self._guided_zone[CONF_AREA_M2])
                    / 60
                )
            else:
                self._guided_zone.pop(CONF_MIN_FLOW, None)
                self._guided_zone.pop(CONF_MAX_FLOW, None)
                self._guided_flow_lpm = None
            return await self.async_step_zone_automatic()
        return self.async_show_form(step_id="zone_rate", data_schema=schema)

    async def async_step_zone_automatic(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Configure one understandable daily window and watering mode."""
        schema = vol.Schema(
            {
                vol.Required("request_automation", default=False): BooleanSelector(),
                vol.Required(CONF_WATERING_MODE, default=WATERING_MODE_DEMAND): _choice(
                    [WATERING_MODE_DEMAND, WATERING_MODE_MINIMUM], CONF_WATERING_MODE
                ),
                vol.Required("window_start", default="04:00:00"): TimeSelector(),
                vol.Required("window_end", default="06:00:00"): TimeSelector(),
            }
        )
        if user_input is not None:
            start = str(user_input["window_start"])[:5]
            end = str(user_input["window_end"])[:5]
            if start == end:
                return self.async_show_form(
                    step_id="zone_automatic",
                    data_schema=schema,
                    errors={"base": "invalid_watering_windows"},
                )
            self._guided_answers.update(user_input)
            self._guided_zone[CONF_WATERING_MODE] = user_input[CONF_WATERING_MODE]
            self._guided_zone[CONF_WATERING_WINDOWS] = [f"{start}-{end}"]
            self._guided_zone[CONF_AUTOMATION_ENABLED] = bool(
                user_input["request_automation"]
            ) and (
                self._guided_answers.get("rate_source") == "measured"
                and self._guided_answers.get("area_method") != "unknown"
            )
            return await self.async_step_zone_cycle_soak()
        return self.async_show_form(step_id="zone_automatic", data_schema=schema)

    async def async_step_zone_cycle_soak(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer a conservative cycle-and-soak suggestion for runoff-prone combinations."""
        soil = str(self._guided_answers.get("soil_answer", "unknown"))
        method = str(self._guided_answers.get("irrigation_method", "drip"))
        suggested = soil in {"clay", "clay_loam"} or method in {"fixed_spray", "rotor"}
        schema = vol.Schema(
            {
                vol.Required("use_cycle_soak", default=suggested): BooleanSelector(),
                vol.Optional("max_dose_minutes", default=10 if suggested else 30): NumberSelector(
                    NumberSelectorConfig(min=1, max=240, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional("soak_minutes", default=20 if suggested else 0): NumberSelector(
                    NumberSelectorConfig(min=0, max=1_440, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        if user_input is not None:
            if user_input["use_cycle_soak"]:
                self._guided_zone[CONF_MAX_DOSE_DURATION] = (
                    float(user_input["max_dose_minutes"]) * 60
                )
                self._guided_zone[CONF_SOAK_DURATION] = float(user_input["soak_minutes"]) * 60
            else:
                self._guided_zone[CONF_SOAK_DURATION] = 0
                self._guided_zone.pop(CONF_MAX_DOSE_DURATION, None)
            return await self.async_step_zone_safety()
        if self.hass.config.language == "de":
            reason = (
                "langsam aufnehmender Boden oder Regner"
                if suggested
                else "Tropfbewässerung und Bodenwahl"
            )
        else:
            reason = "slow soil or sprinkler application" if suggested else "drip/soil combination"
        return self.async_show_form(
            step_id="zone_cycle_soak",
            data_schema=schema,
            description_placeholders={"recommendation": reason},
        )

    async def async_step_zone_safety(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Set finite automatic limits in user-facing units."""
        schema = vol.Schema(
            {
                vol.Required("automatic_max_minutes", default=60): NumberSelector(
                    NumberSelectorConfig(min=1, max=240, step=1, mode=NumberSelectorMode.BOX)
                ),
                vol.Required(CONF_MAXIMUM_TARGET_LITERS, default=1_000): NumberSelector(
                    NumberSelectorConfig(min=1, max=1_000_000, step=1, mode=NumberSelectorMode.BOX)
                ),
            }
        )
        if user_input is not None:
            seconds = float(user_input["automatic_max_minutes"]) * 60
            self._guided_zone[CONF_AUTOMATIC_MAX_DURATION] = seconds
            self._guided_zone[CONF_MAX_DELIVERY_RUNTIME] = seconds
            self._guided_zone[CONF_MAX_OPERATION_LIFETIME] = max(seconds * 2, seconds + 600)
            self._guided_zone[CONF_MAXIMUM_TARGET_LITERS] = user_input[CONF_MAXIMUM_TARGET_LITERS]
            return await self.async_step_zone_review()
        return self.async_show_form(step_id="zone_safety", data_schema=schema)

    async def async_step_zone_review(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Preview profile impact and save only after local confirmation."""
        custom = self._get_entry().data.get(CONF_CUSTOM_PROFILES, {})
        normalized = dict(ZONE_SCHEMA(self._guided_zone))
        normalized[CONF_AGRONOMIC_VALUES_CONFIRMED] = False
        preview = _plain_profile_preview(
            normalized, custom, self.hass.config.language, self._guided_flow_lpm
        )
        if self._guided_answers.get("area_method") == "unknown":
            preview += (
                " Die Fläche ist mit 1 m² vorläufig; vor der Automatikfreigabe messen."
                if self.hass.config.language == "de"
                else " Area is provisional (1 m2); measure it before enabling automation."
            )
        if self._guided_answers.get("soil_answer") == "unknown":
            preview += (
                " Unbekannter Boden verwendet konservativ Sand, den niedrigsten erforschten "
                "Wasserspeicher-Standard; vor Ort prüfen."
                if self.hass.config.language == "de"
                else " Unknown soil conservatively uses sand, the lowest researched water-storage "
                "default; confirm it on site."
            )
        preview += (
            " Die Standortangabe ist nur beschreibend; ohne lokale Belege wird der Wasserbedarf "
            "nicht automatisch reduziert."
            if self.hass.config.language == "de"
            else " Exposure is descriptive only; no automatic demand reduction is applied without "
            "local evidence."
        )
        if (
            self._guided_answers.get("request_automation")
            and not normalized[CONF_AUTOMATION_ENABLED]
        ):
            preview += (
                " Automatik bleibt gesperrt, bis Fläche und gemessener Durchfluss bereit sind."
                if self.hass.config.language == "de"
                else " Automatic release remains blocked until area and measured flow are ready."
            )
        if user_input is None:
            return self.async_show_form(
                step_id="zone_review",
                data_schema=vol.Schema(
                    {vol.Required("confirm_profile_selection", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": preview},
            )
        if user_input.get("confirm_profile_selection") is not True:
            return await self.async_step_zone_profiles()
        normalized[CONF_AGRONOMIC_VALUES_CONFIRMED] = True
        if error := _validate_zone_input(normalized, custom):
            return self.async_abort(reason=error)
        if self._pending_reconfigure:
            return self.async_update_and_abort(
                self._get_entry(),
                self._get_reconfigure_subentry(),
                title=str(normalized[CONF_NAME]),
                data=normalized,
            )
        return self.async_create_entry(
            title=str(normalized[CONF_NAME]), data=normalized, unique_id=uuid4().hex
        )

    async def async_step_profile_confirmation(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Show provenance and resolved deficit before saving a researched profile."""
        pending = self._pending_zone_input
        if pending is None:
            return self.async_abort(reason="profile_selection_not_pending")
        if user_input is None:
            return self.async_show_form(
                step_id="profile_confirmation",
                data_schema=vol.Schema(
                    {vol.Required("confirm_profile_selection", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": self._profile_preview},
            )
        if user_input.get("confirm_profile_selection") is not True:
            return self.async_abort(reason="profile_selection_cancelled")
        self._pending_zone_input = None
        if self._pending_reconfigure:
            entry = self._get_entry()
            subentry = self._get_reconfigure_subentry()
            return self.async_update_and_abort(
                entry,
                subentry,
                title=str(pending[CONF_NAME]),
                data=pending,
            )
        return self.async_create_entry(
            title=str(pending[CONF_NAME]), data=pending, unique_id=uuid4().hex
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
        self._import_profiles_confirmed = False
        self._pending_zone_input: dict[str, Any] | None = None
        self._zone_profile_preview = ""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer progressive guidance without removing expert access."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["guided", "expert", "import_config"],
        )

    async def async_step_guided(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer manageable plain-language edit groups."""
        return self.async_show_menu(
            step_id="guided", menu_options=["guided_installation", "guided_zone"]
        )

    async def async_step_expert(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Expose the complete compatible stored model."""
        return self.async_show_menu(step_id="expert", menu_options=["installation", "zone"])

    async def async_step_guided_installation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit common installation choices while preserving hidden expert fields."""
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Optional(CONF_MAIN_VALVE): EntitySelector(
                    EntitySelectorConfig(domain=[Platform.SWITCH, Platform.VALVE])
                ),
                vol.Optional(CONF_MAIN_VALVE_FEEDBACK): EntitySelector(
                    EntitySelectorConfig(
                        domain=[Platform.BINARY_SENSOR, Platform.SWITCH, Platform.VALVE]
                    )
                ),
                vol.Optional(CONF_WATER_METER): EntitySelector(
                    EntitySelectorConfig(domain=Platform.SENSOR)
                ),
                vol.Optional(CONF_FLOW_SENSOR): EntitySelector(
                    EntitySelectorConfig(domain=Platform.SENSOR)
                ),
                vol.Optional(CONF_WEATHER_ENTITY): EntitySelector(
                    EntitySelectorConfig(domain=Platform.WEATHER)
                ),
                vol.Optional(CONF_OPEN_METEO_ENABLED): BooleanSelector(),
                vol.Required(CONF_HARDWARE_SHUTOFF_ACKNOWLEDGED): BooleanSelector(),
                vol.Required(CONF_AUTOMATION_ENABLED): BooleanSelector(),
            }
        )
        if user_input is not None:
            merged = dict(INSTALLATION_SCHEMA({**self.config_entry.data, **user_input}))
            if error := _validate_installation_input(merged):
                return self.async_show_form(
                    step_id="guided_installation",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": error},
                )
            self._installation_config_hash = IrrigationManager.installation_config_hash(
                self.config_entry.data
            )
            return await self._save_installation(merged)
        return self.async_show_form(
            step_id="guided_installation",
            data_schema=self.add_suggested_values_to_schema(schema, self.config_entry.data),
        )

    async def async_step_guided_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select a zone for a guided profile-aware edit."""
        zones = self.config_entry.get_subentries_of_type(SUBENTRY_TYPE_ZONE)
        if not zones:
            return self.async_abort(reason="no_zones")
        if user_input is not None:
            self._zone_subentry_id = str(user_input[ATTR_ZONE_SUBENTRY_ID])
            return await self.async_step_guided_zone_settings()
        return self.async_show_form(
            step_id="guided_zone",
            data_schema=vol.Schema(
                {
                    vol.Required(ATTR_ZONE_SUBENTRY_ID): SelectSelector(
                        SelectSelectorConfig(
                            options=cast(
                                Any,
                                [
                                    {"value": item.subentry_id, "label": item.title}
                                    for item in zones
                                ],
                            )
                        )
                    )
                }
            ),
        )

    async def async_step_guided_zone_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit high-impact zone values and preview their water-model effect."""
        subentry = self.config_entry.subentries.get(self._zone_subentry_id or "")
        if subentry is None:
            return self.async_abort(reason="zone_not_found")
        custom = self.config_entry.data.get(CONF_CUSTOM_PROFILES, {})
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): TextSelector(),
                vol.Required(CONF_AREA_M2): NumberSelector(
                    NumberSelectorConfig(
                        min=0.1, max=100_000, step=0.1, mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_PLANT_PROFILE): SelectSelector(
                    SelectSelectorConfig(
                        options=cast(
                            Any, profile_select_options(custom, "plant", self.hass.config.language)
                        )
                    )
                ),
                vol.Required(CONF_SOIL_PROFILE): SelectSelector(
                    SelectSelectorConfig(
                        options=cast(
                            Any, profile_select_options(custom, "soil", self.hass.config.language)
                        )
                    )
                ),
                vol.Required(CONF_IRRIGATION_PROFILE): SelectSelector(
                    SelectSelectorConfig(
                        options=cast(
                            Any,
                            profile_select_options(custom, "irrigation", self.hass.config.language),
                        )
                    )
                ),
                vol.Optional(CONF_MIN_FLOW): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_MAX_FLOW): NumberSelector(
                    NumberSelectorConfig(min=0.1, max=10_000, step=0.1, mode=NumberSelectorMode.BOX)
                ),
                vol.Optional(CONF_AUTOMATION_ENABLED, default=False): BooleanSelector(),
            }
        )
        if user_input is not None:
            merged_input = {**subentry.data, **user_input}
            _clear_stale_profile_overrides(merged_input, subentry.data)
            merged = dict(ZONE_SCHEMA(merged_input))
            if error := _validate_zone_input(merged, custom):
                return self.async_show_form(
                    step_id="guided_zone_settings",
                    data_schema=self.add_suggested_values_to_schema(schema, user_input),
                    errors={"base": error},
                )
            flow = (
                (float(merged[CONF_MIN_FLOW]) + float(merged[CONF_MAX_FLOW])) / 2
                if merged.get(CONF_MIN_FLOW) and merged.get(CONF_MAX_FLOW)
                else None
            )
            self._pending_zone_input = merged
            self._zone_profile_preview = _plain_profile_preview(
                merged, custom, self.hass.config.language, flow
            )
            return await self.async_step_zone_profile_confirmation()
        return self.async_show_form(
            step_id="guided_zone_settings",
            data_schema=self.add_suggested_values_to_schema(schema, subentry.data),
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
            self._import_profiles_confirmed = False
            if preview.get("profile_confirmation_required") is True:
                return await self.async_step_import_profile_confirmation()
            return await self.async_step_import_confirm()
        return self.async_show_form(step_id="import_config", data_schema=self._import_schema())

    async def async_step_import_profile_confirmation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Require local review of researched profiles before overwrite confirmation."""
        if self._pending_import is None:
            return self.async_abort(reason="import_not_pending")
        if user_input is None:
            return self.async_show_form(
                step_id="import_profile_confirmation",
                data_schema=vol.Schema(
                    {vol.Required("confirm_researched_profiles", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": self._import_preview},
            )
        if user_input.get("confirm_researched_profiles") is not True:
            self._pending_import = None
            return self.async_abort(reason="profile_selection_cancelled")
        self._import_profiles_confirmed = True
        return await self.async_step_import_confirm()

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
                    confirm_researched_profiles=self._import_profiles_confirmed,
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
                    data_schema=self.add_suggested_values_to_schema(
                        _zone_schema(
                            self.config_entry.data.get(CONF_CUSTOM_PROFILES, {}),
                            self.hass.config.language,
                        ),
                        user_input,
                    ),
                    errors={"base": error},
                )
            if any(
                other.subentry_id != subentry.subentry_id
                and other.data.get(CONF_ZONE_VALVE) == user_input[CONF_ZONE_VALVE]
                for other in self.config_entry.subentries.values()
            ):
                return self.async_abort(reason="already_configured")
            preview, required = _profile_preview(
                user_input,
                self.config_entry.data.get(CONF_CUSTOM_PROFILES, {}),
                self.hass.config.language,
            )
            if required:
                self._pending_zone_input = user_input
                self._zone_profile_preview = preview
                return await self.async_step_zone_profile_confirmation()
            self.hass.config_entries.async_update_subentry(
                self.config_entry,
                subentry,
                title=str(user_input[CONF_NAME]),
                data=user_input,
            )
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="zone_settings",
            data_schema=self.add_suggested_values_to_schema(
                _zone_schema(
                    self.config_entry.data.get(CONF_CUSTOM_PROFILES, {}),
                    self.hass.config.language,
                ),
                subentry.data,
            ),
        )

    async def async_step_zone_profile_confirmation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a zone's researched profile and derived TAW/RAW limits."""
        pending = self._pending_zone_input
        subentry = self.config_entry.subentries.get(self._zone_subentry_id or "")
        if pending is None or subentry is None:
            return self.async_abort(reason="profile_selection_not_pending")
        if user_input is None:
            return self.async_show_form(
                step_id="zone_profile_confirmation",
                data_schema=vol.Schema(
                    {vol.Required("confirm_profile_selection", default=False): BooleanSelector()}
                ),
                description_placeholders={"preview": self._zone_profile_preview},
            )
        if user_input.get("confirm_profile_selection") is not True:
            return self.async_abort(reason="profile_selection_cancelled")
        self._pending_zone_input = None
        self.hass.config_entries.async_update_subentry(
            self.config_entry,
            subentry,
            title=str(pending[CONF_NAME]),
            data=pending,
        )
        return self.async_create_entry(data={})
