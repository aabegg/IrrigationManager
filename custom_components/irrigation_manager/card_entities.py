"""Bounded entity-registry mappings for the bundled Lovelace cards."""

from collections.abc import Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN

INSTALLATION_CARD_ROLES: Mapping[str, tuple[str, str]] = {
    "status": ("sensor", "status"),
    "emergency": ("binary_sensor", "emergency_stop"),
    "lock": ("binary_sensor", "safety_lock"),
    "active_zone": ("sensor", "active_zone"),
    "dose": ("sensor", "current_dose"),
    "pending": ("sensor", "pending_requests"),
    "next": ("sensor", "next_zone"),
    "today_consumption": ("sensor", "water_today"),
    "month_consumption": ("sensor", "water_month"),
    "model_quality": ("sensor", "weather_model_quality"),
    "winter": ("binary_sensor", "winter_lock"),
    "maintenance": ("binary_sensor", "maintenance_mode"),
    "automation_release": ("binary_sensor", "automation_release"),
    "maintenance_due": ("sensor", "maintenance_due"),
}

ZONE_CARD_ROLES: Mapping[str, tuple[str, str]] = {
    "zone": ("sensor", "water_total"),
    "automation_needed": ("binary_sensor", "automation_needed"),
    "safety_lock": ("binary_sensor", "safety_lock"),
    "deficit": ("sensor", "water_deficit"),
    "target": ("sensor", "automatic_target"),
    "planning_reason": ("sensor", "planning_reason"),
    "next_window": ("sensor", "next_watering_window"),
    "last_delivered": ("sensor", "last_delivered"),
    "last_duration": ("sensor", "last_duration"),
    "quality": ("sensor", "measurement_quality"),
    "status": ("sensor", "zone_status"),
    "automation_release": ("binary_sensor", "automation_release"),
    "archived": ("binary_sensor", "archived"),
    "coverage": ("sensor", "demand_coverage"),
    "expected_flow": ("sensor", "expected_flow"),
    "actual_flow": ("sensor", "actual_flow"),
    "flow_deviation": ("sensor", "flow_deviation"),
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
