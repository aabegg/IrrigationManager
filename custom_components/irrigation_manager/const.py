"""Constants consumed by the version-2 integration."""

from typing import Final

DOMAIN: Final = "irrigation_manager"
INTEGRATION_NAME: Final = "Irrigation Manager"

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
CONF_WEEKLY_SCHEDULE: Final = "weekly_schedule"
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
