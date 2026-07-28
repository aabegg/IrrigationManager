"""Diagnostics support for the authoritative version-2 runtime."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_MAIN_VALVE, CONF_METER_ENTITY, CONF_ZONE_VALVE
from .runtime import IrrigationConfigEntry

TO_REDACT = {"name", CONF_MAIN_VALVE, CONF_METER_ENTITY, CONF_ZONE_VALVE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrrigationConfigEntry
) -> dict[str, Any]:
    """Return redacted configuration and the decisions behind current state."""
    manager = entry.runtime_data.manager
    decisions = manager.diagnostics_state_decisions()
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
    }
