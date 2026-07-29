"""Constants consumed by the version-2 integration."""

from typing import Final

DOMAIN: Final = "irrigation_manager"
INTEGRATION_NAME: Final = "Irrigation Manager"
CONFIG_ENTRY_VERSION: Final = 2
CONFIG_ENTRY_MINOR_VERSION: Final = 7

CONF_MAIN_VALVE: Final = "main_valve"
CONF_WATER_METER: Final = "water_meter"
CONF_RAW_METER: Final = "raw_meter"
CONF_LITERS_PER_COUNT: Final = "liters_per_count"
CONF_METER_TYPE: Final = "meter_type"
CONF_METER_ENTITY: Final = "meter_entity"
CONF_LITERS_PER_PULSE: Final = "liters_per_pulse"
CONF_ZONE_VALVE: Final = "zone_valve"
CONF_AUTOMATION_ENABLED: Final = "automation_enabled"
CONF_OPERATION_ENABLED: Final = "operation_enabled"
CONF_NEEDS_RECONFIGURATION: Final = "needs_reconfiguration"
CONF_CONTROL_TYPE: Final = "control_type"
CONF_BASE_TARGET: Final = "base_target"
CONF_WEEKLY_SCHEDULE: Final = "weekly_schedule"
CONF_PLANT_SITE_MODULE_ENABLED: Final = "plant_site_module_enabled"
CONF_SEASONAL_MODULE_ENABLED: Final = "seasonal_module_enabled"
CONF_USE_SEASONAL_ADJUSTMENT: Final = "use_seasonal_adjustment"
CONF_SEASONAL_FACTORS: Final = "seasonal_factors"
CONF_WEATHER_MODULE_ENABLED: Final = "weather_module_enabled"
CONF_WEATHER_SOURCES: Final = "weather_sources"
CONF_USE_WEATHER_ADJUSTMENT: Final = "use_weather_adjustment"
CONF_USE_FORECAST_POSTPONEMENT: Final = "use_forecast_postponement"
CONF_USE_SOIL_MOISTURE_FEEDBACK: Final = "use_soil_moisture_feedback"
CONF_SOIL_MOISTURE_ASSIGNMENTS: Final = "soil_moisture_assignments"
CONF_SOIL_MOISTURE_ACTIVATION_ID: Final = "soil_moisture_activation_id"
CONF_MAXIMUM_MAKE_UP_DAYS: Final = "maximum_make_up_days"
CONF_MAKE_UP_SCHEDULE: Final = "make_up_schedule"
CONF_MINIMUM_FORECAST_PRECIPITATION_MM: Final = "minimum_forecast_precipitation_mm"
CONF_MINIMUM_FORECAST_PROBABILITY: Final = "minimum_forecast_probability"
CONF_MAXIMUM_MAKE_UP_TARGET: Final = "maximum_make_up_target"
CONF_WATERING_MODE: Final = "watering_mode"
CONF_CROP_FACTOR: Final = "crop_factor"
CONF_EFFECTIVE_RAIN_FACTOR: Final = "effective_rain_factor"
CONF_DEMAND_THRESHOLD_MM: Final = "demand_threshold_mm"
CONF_MAXIMUM_DEFICIT_MM: Final = "maximum_deficit_mm"
CONF_EFFECTIVE_APPLICATION_RATE_MM_H: Final = "effective_application_rate_mm_h"
CONF_IRRIGATED_AREA_M2: Final = "irrigated_area_m2"
CONF_IRRIGATION_EFFICIENCY: Final = "irrigation_efficiency"
CONF_SOAK_MODULE_ENABLED: Final = "soak_module_enabled"
CONF_USE_PLANT_SITE_MODEL: Final = "use_plant_site_model"
CONF_SUBAREAS: Final = "subareas"
CONF_VOLUME_MAX_RUNTIME: Final = "volume_max_runtime"
CONF_EXPECTED_FLOW_L_MIN: Final = "expected_flow_l_min"
CONF_MAX_DELIVERY_RUNTIME: Final = "max_delivery_runtime"
CONF_MAX_OPERATION_LIFETIME: Final = "max_operation_lifetime"
CONF_CALIBRATION_SETTLE_SECONDS: Final = "calibration_settle_seconds"
CONF_CALIBRATION_MAX_DURATION: Final = "calibration_max_duration"
CONF_CALIBRATION_CONFIRMATION_INTERVAL: Final = "calibration_confirmation_interval"

SUBENTRY_TYPE_ZONE: Final = "zone"
METER_TYPE_NONE: Final = "none"
METER_TYPE_CUMULATIVE: Final = "cumulative"
METER_TYPE_PULSE: Final = "pulse"
CONTROL_TYPE_TIME: Final = "time"
CONTROL_TYPE_VOLUME: Final = "volume"
WEEKDAYS: Final = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
