"""Diagnostics support for Irrigation Manager."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ET0_SENSORS,
    CONF_EXTERNAL_BLOCK,
    CONF_EXTERNAL_PERMIT,
    CONF_FLOW_SENSOR,
    CONF_FROST_ENTITY,
    CONF_HARDWARE_BATTERY_SENSOR,
    CONF_HARDWARE_CONNECTIVITY_SENSOR,
    CONF_HARDWARE_FAULT_SENSOR,
    CONF_HUMIDITY_SENSORS,
    CONF_MAIN_VALVE,
    CONF_MAIN_VALVE_FEEDBACK,
    CONF_NOTIFY_ENTITIES,
    CONF_PRESSURE_SENSORS,
    CONF_RAIN_SENSORS,
    CONF_RAIN_STOP_ENTITY,
    CONF_SOIL_MOISTURE_SENSORS,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_SUNSHINE_DURATION_SENSORS,
    CONF_TEMPERATURE_SENSORS,
    CONF_WATER_METER,
    CONF_WEATHER_ENTITY,
    CONF_WIND_INTERLOCK_ENTITY,
    CONF_WIND_SPEED_SENSORS,
    CONF_ZONE_VALVE,
    CONF_ZONE_VALVE_FEEDBACK,
    PROFILE_CATALOG_VERSION,
)
from .profiles import builtin_profiles, profile_selection_summary
from .runtime import IrrigationConfigEntry

TO_REDACT = {
    "name",
    CONF_MAIN_VALVE,
    CONF_MAIN_VALVE_FEEDBACK,
    CONF_WATER_METER,
    CONF_FLOW_SENSOR,
    CONF_EXTERNAL_PERMIT,
    CONF_EXTERNAL_BLOCK,
    CONF_FROST_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_RAIN_STOP_ENTITY,
    CONF_ZONE_VALVE,
    CONF_ZONE_VALVE_FEEDBACK,
    CONF_NOTIFY_ENTITIES,
    CONF_TEMPERATURE_SENSORS,
    CONF_HUMIDITY_SENSORS,
    CONF_WIND_SPEED_SENSORS,
    CONF_WIND_INTERLOCK_ENTITY,
    CONF_SOLAR_RADIATION_SENSORS,
    CONF_SUNSHINE_DURATION_SENSORS,
    CONF_PRESSURE_SENSORS,
    CONF_RAIN_SENSORS,
    CONF_ET0_SENSORS,
    CONF_HARDWARE_BATTERY_SENSOR,
    CONF_HARDWARE_CONNECTIVITY_SENSOR,
    CONF_HARDWARE_FAULT_SENSOR,
    CONF_SOIL_MOISTURE_SENSORS,
}


def _profile_diagnostics(entry: IrrigationConfigEntry) -> list[dict[str, object]]:
    """Resolve profile provenance without making diagnostics fail on stale configuration."""
    result: list[dict[str, object]] = []
    for subentry in entry.subentries.values():
        try:
            selection: object = profile_selection_summary(
                subentry.data,
                entry.data.get("custom_profiles", {}),
                dt_util.now().date(),
            )
        except (TypeError, ValueError) as err:
            selection = {"error": str(err)}
        result.append({"subentry_id": subentry.subentry_id, "selection": selection})
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrrigationConfigEntry
) -> dict[str, Any]:
    """Return redacted configuration and the decisions behind current state."""
    manager = entry.runtime_data.manager
    return {
        "entry": async_redact_data(
            {
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            TO_REDACT,
        ),
        "zones": [
            async_redact_data(
                {
                    "subentry_id": subentry.subentry_id,
                    "unique_id": subentry.unique_id,
                    "data": dict(subentry.data),
                },
                TO_REDACT,
            )
            for subentry in entry.subentries.values()
        ],
        "state_decisions": manager.diagnostics_state_decisions(),
        "profile_catalog": {
            "version": PROFILE_CATALOG_VERSION,
            "built_in": builtin_profiles(),
            "resolved_zones": _profile_diagnostics(entry),
        },
    }
