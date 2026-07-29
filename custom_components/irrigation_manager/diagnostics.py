"""Diagnostics support for the authoritative version-2 runtime."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_SOIL_MOISTURE_ACTIVATION_ID,
    CONF_SOIL_MOISTURE_ASSIGNMENTS,
    CONF_SUBAREAS,
    CONF_USE_SOIL_MOISTURE_FEEDBACK,
    CONF_USE_WEATHER_ADJUSTMENT,
    CONF_WEATHER_MODULE_ENABLED,
    CONF_WEATHER_SOURCES,
    CONF_ZONE_VALVE,
)
from .runtime import IrrigationConfigEntry
from .soil_moisture import observe_soil_moisture
from .weather_sources import observe_weather_sources

TO_REDACT = {
    "name",
    "source_entity_id",
    "source_entity_ids",
    "calibration_signature",
    "entity_id",
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_SOIL_MOISTURE_ASSIGNMENTS,
    CONF_SOIL_MOISTURE_ACTIVATION_ID,
    CONF_WEATHER_SOURCES,
    CONF_ZONE_VALVE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrrigationConfigEntry
) -> dict[str, Any]:
    """Return redacted configuration and the decisions behind current state."""
    manager = entry.runtime_data.manager
    decisions = manager.diagnostics_state_decisions()
    weather_sources = {
        "weather_correction_enabled": bool(entry.data.get(CONF_WEATHER_MODULE_ENABLED, False)),
        "observations": observe_weather_sources(
            hass,
            entry.data.get(CONF_WEATHER_SOURCES, {}),
        ),
    }
    soil_moisture = []
    for subentry in entry.subentries.values():
        assignments = subentry.data.get(CONF_SOIL_MOISTURE_ASSIGNMENTS, [])
        soil_moisture.append(
            {
                "subentry_id": subentry.subentry_id,
                "feedback_enabled": bool(
                    entry.data.get(CONF_WEATHER_MODULE_ENABLED, False)
                    and subentry.data.get(CONF_USE_WEATHER_ADJUSTMENT, False)
                    and subentry.data.get(CONF_USE_SOIL_MOISTURE_FEEDBACK, False)
                ),
                "observation": observe_soil_moisture(
                    hass,
                    assignments,
                    subentry.data.get(CONF_SUBAREAS),
                    activation_id=subentry.data.get(CONF_SOIL_MOISTURE_ACTIVATION_ID),
                ).as_dict(),
            }
        )
    redacted_decisions = async_redact_data(decisions, TO_REDACT)
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
        "state_decisions": redacted_decisions,
        "dispatcher": redacted_decisions["dispatcher"],
        "dispatcher_history": redacted_decisions["dispatcher_history"],
        "weather_sources": async_redact_data(weather_sources, TO_REDACT),
        "soil_moisture": async_redact_data(soil_moisture, TO_REDACT),
    }
