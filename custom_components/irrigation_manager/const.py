"""Constants for Irrigation Manager."""

from typing import Final

DOMAIN: Final = "irrigation_manager"
INTEGRATION_NAME: Final = "Irrigation Manager"

CONF_MAIN_VALVE: Final = "main_valve"
CONF_WATER_METER: Final = "water_meter"
CONF_FLOW_SENSOR: Final = "flow_sensor"
CONF_FLOW_MAX_AGE_SECONDS: Final = "flow_max_age_seconds"
CONF_LEAK_MONITORING: Final = "leak_monitoring"
CONF_LEAK_FLOW_THRESHOLD: Final = "leak_flow_threshold"
CONF_LEAK_DURATION_SECONDS: Final = "leak_duration_seconds"
CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_ZONE_VALVE: Final = "zone_valve"
CONF_DEFAULT_DURATION: Final = "default_duration"
CONF_MIN_FLOW: Final = "min_flow"
CONF_MAX_FLOW: Final = "max_flow"
CONF_FLOW_GRACE_SECONDS: Final = "flow_grace_seconds"
CONF_METER_FAILURE_STRATEGY: Final = "meter_failure_strategy"

METER_FAILURE_ABORT: Final = "abort"
METER_FAILURE_ESTIMATED_TIME_FALLBACK: Final = "estimated_time_fallback"

SUBENTRY_TYPE_ZONE: Final = "zone"
