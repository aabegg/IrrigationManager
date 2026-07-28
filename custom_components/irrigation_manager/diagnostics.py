"""Diagnostics support for the authoritative version-2 runtime."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import (
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
    CONF_WEATHER_MODULE_ENABLED,
    CONF_WEATHER_SOURCES,
    CONF_ZONE_VALVE,
)
from .runtime import IrrigationConfigEntry
from .weather_sources import observe_weather_sources

TO_REDACT = {
    "name",
    "source_entity_id",
    CONF_MAIN_VALVE,
    CONF_METER_ENTITY,
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
        "state_decisions": decisions,
        "dispatcher": decisions["dispatcher"],
        "dispatcher_history": decisions["dispatcher_history"],
        "weather_sources": async_redact_data(weather_sources, TO_REDACT),
    }
