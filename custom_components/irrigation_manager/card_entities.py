"""Bounded entity-registry mappings for the bundled Lovelace cards."""

from collections.abc import Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

INSTALLATION_CARD_ROLES: Mapping[str, tuple[str, str]] = {
    "status": ("sensor", "status"),
    "emergency": ("binary_sensor", "emergency_stop"),
    "lock": ("binary_sensor", "safety_lock"),
    "pending": ("sensor", "pending_requests"),
    "next": ("sensor", "next_zone"),
    "next_start": ("sensor", "next_start"),
    "today_consumption": ("sensor", "water_today"),
    "month_consumption": ("sensor", "water_month"),
    "runtime_today": ("sensor", "runtime_today"),
    "runtime_month": ("sensor", "runtime_month"),
    "physical_meter": ("sensor", "physical_meter"),
}

ZONE_CARD_ROLES: Mapping[str, tuple[str, str]] = {
    "anchor": ("sensor", "zone_status"),
    "status": ("sensor", "zone_status"),
    "water_today": ("sensor", "water_today"),
    "water_month": ("sensor", "water_month"),
    "runtime_today": ("sensor", "runtime_today"),
    "runtime_month": ("sensor", "runtime_month"),
    "next_irrigation": ("sensor", "next_irrigation"),
}


def registry_card_entities(
    hass: HomeAssistant,
    stable_id: str,
    roles: Mapping[str, tuple[str, str]],
) -> dict[str, str]:
    """Resolve an allow-list of semantic roles through stable unique IDs."""
    registry = er.async_get(hass)
    result: dict[str, str] = {}
    for role, (entity_domain, suffix) in roles.items():
        entity_id = registry.async_get_entity_id(entity_domain, DOMAIN, f"{stable_id}_{suffix}")
        if entity_id is not None:
            result[role] = entity_id
    return result
