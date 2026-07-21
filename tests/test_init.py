"""Home Assistant lifecycle tests for Irrigation Manager."""

import asyncio
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.models import StoredInstallationState
from custom_components.irrigation_manager.storage import IrrigationStore


async def test_setup_closes_an_open_main_valve(hass: HomeAssistant) -> None:
    """Recover to a hydraulically closed state when an installation loads."""
    operations: list[str] = []

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(entity_id)
        hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_ON)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung", "main_valve": "switch.main"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert operations == ["switch.main"]
    assert hass.states.get("switch.main").state == STATE_OFF


async def test_setup_creates_installation_and_zone_water_sensors(
    hass: HomeAssistant,
) -> None:
    """Expose cumulative water sensors with stable registry identities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Rasen",
                "zone_valve": "switch.relais_11",
                "default_duration": 600,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    installation_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_water_total"
    )
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")

    assert installation_entity_id is not None
    assert zone_entity_id is not None
    assert hass.states.get(installation_entity_id).state == "0.0"
    assert hass.states.get(zone_entity_id).state == "0.0"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_manual_timed_action_controls_valves_and_attributes_water(
    hass: HomeAssistant,
) -> None:
    """Run a manual dose through HA services and publish measured consumption."""
    operations: list[tuple[str, str]] = []

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_on", entity_id))
        hass.states.async_set(entity_id, STATE_ON)

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_off", entity_id))
        hass.states.async_set(entity_id, STATE_OFF)
        if entity_id == "switch.zone_lawn":
            hass.states.async_set(
                "sensor.water_meter",
                "1.025",
                {ATTR_UNIT_OF_MEASUREMENT: "m³"},
            )

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set("switch.zone_lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.water_meter",
        "1.000",
        {ATTR_UNIT_OF_MEASUREMENT: "m³"},
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "water_meter": "sensor.water_meter",
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Rasen",
                "zone_valve": "switch.zone_lawn",
                "default_duration": 600,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "duration": 0.001,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    installation_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_water_total"
    )
    assert zone_entity_id is not None
    assert installation_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "25.0"
    assert hass.states.get(zone_entity_id).attributes["measurement_quality"] == "measured"
    assert hass.states.get(installation_entity_id).state == "25.0"
    assert operations == [
        ("turn_on", "switch.main"),
        ("turn_on", "switch.zone_lawn"),
        ("turn_off", "switch.zone_lawn"),
        ("turn_off", "switch.main"),
    ]


async def test_stop_action_closes_active_valves_and_accounts_partial_water(
    hass: HomeAssistant,
) -> None:
    """Stop an active manual dose without leaving a valve open."""
    zone_opened = asyncio.Event()
    operations: list[tuple[str, str]] = []

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_on", entity_id))
        hass.states.async_set(entity_id, STATE_ON)
        if entity_id == "switch.zone_lawn":
            zone_opened.set()

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_off", entity_id))
        hass.states.async_set(entity_id, STATE_OFF)
        if entity_id == "switch.zone_lawn":
            hass.states.async_set(
                "sensor.water_meter",
                "1.025",
                {ATTR_UNIT_OF_MEASUREMENT: "m³"},
            )

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set("switch.zone_lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.water_meter",
        "1.000",
        {ATTR_UNIT_OF_MEASUREMENT: "m³"},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "water_meter": "sensor.water_meter",
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Rasen",
                "zone_valve": "switch.zone_lawn",
                "default_duration": 600,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "duration": 3_600,
        },
        blocking=False,
    )
    await zone_opened.wait()
    await hass.services.async_call(
        DOMAIN,
        "stop",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    assert zone_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "25.0"
    assert operations == [
        ("turn_on", "switch.main"),
        ("turn_on", "switch.zone_lawn"),
        ("turn_off", "switch.zone_lawn"),
        ("turn_off", "switch.main"),
    ]


async def test_assign_water_moves_unassigned_consumption_to_zone(
    hass: HomeAssistant,
) -> None:
    """Attribute measured water without changing installation consumption."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Rasen",
                "zone_valve": "switch.zone_lawn",
                "default_duration": 600,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(
            installation_total_liters=10,
            unassigned_total_liters=10,
        )
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        "assign_water",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "amount": 4,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    installation_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_water_total"
    )
    unassigned_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_unassigned_water_total"
    )
    assert zone_entity_id is not None
    assert installation_entity_id is not None
    assert unassigned_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "4.0"
    assert hass.states.get(zone_entity_id).attributes["measurement_quality"] == "measured"
    assert hass.states.get(installation_entity_id).state == "10.0"
    assert hass.states.get(unassigned_entity_id).state == "6.0"


async def test_emergency_stop_blocks_manual_watering(hass: HomeAssistant) -> None:
    """Never allow a normal manual request to override the safety lock."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Rasen",
                "zone_valve": "switch.zone_lawn",
                "default_duration": 600,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    await IrrigationStore(hass, entry.entry_id).async_save(
        StoredInstallationState(emergency_stop=True)
    )
    assert await hass.config_entries.async_setup(entry.entry_id)

    with pytest.raises(HomeAssistantError, match="emergency stop"):
        await hass.services.async_call(
            DOMAIN,
            "start_manual",
            {
                "config_entry_id": entry.entry_id,
                "zone_subentry_id": subentry.subentry_id,
                "duration": 60,
            },
            blocking=True,
        )
