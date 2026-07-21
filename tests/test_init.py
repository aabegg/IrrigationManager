"""Home Assistant lifecycle tests for Irrigation Manager."""

import asyncio
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    StoredInstallationState,
)
from custom_components.irrigation_manager.storage import IrrigationStore


def prepare_closed_switches(hass: HomeAssistant, *entity_ids: str) -> None:
    """Register deterministic switch closure feedback for setup tests."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    for entity_id in entity_ids:
        hass.states.async_set(entity_id, STATE_OFF)


async def test_storage_migrates_legacy_state(hass: HomeAssistant) -> None:
    """Preserve totals when adding durable active-execution recovery state."""
    await Store[dict[str, object]](
        hass, 1, "irrigation_manager.legacy", atomic_writes=True
    ).async_save(
        {
            "installation_total_liters": 12.0,
            "zone_totals_liters": {"zone-1": 12.0},
            "zone_measurement_quality": {"zone-1": "measured"},
            "unassigned_total_liters": 0.0,
            "emergency_stop": False,
        }
    )

    state = await IrrigationStore(hass, "legacy").async_load()

    assert state.installation_total_liters == 12
    assert state.zone_totals_liters == {"zone-1": 12}
    assert state.active_execution is None
    assert state.idle_meter_raw_baseline_liters is None
    assert state.unassigned_measurement_quality == "unknown"
    assert state.unassigned_measurement_origin == "unknown"


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
    prepare_closed_switches(hass, "switch.relais_11")
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
    persisted_zone_at_open: list[str | None] = []

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_on", entity_id))
        hass.states.async_set(entity_id, STATE_ON)
        if entity_id == "switch.zone_lawn":
            stored = await IrrigationStore(hass, entry.entry_id).async_load()
            persisted_zone_at_open.append(
                stored.active_execution.zone_id if stored.active_execution is not None else None
            )

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(("turn_off", entity_id))
        was_on = hass.states.get(entity_id).state == STATE_ON
        hass.states.async_set(entity_id, STATE_OFF)
        if entity_id == "switch.zone_lawn" and was_on:
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
    operations.clear()

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
    status_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "installation-1_status")
    active_zone_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_active_zone"
    )
    last_delivered_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "zone-1_last_delivered"
    )
    last_duration_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_last_duration")
    quality_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_measurement_quality")
    assert zone_entity_id is not None
    assert installation_entity_id is not None
    assert status_entity_id is not None
    assert active_zone_entity_id is not None
    assert last_delivered_entity_id is not None
    assert last_duration_entity_id is not None
    assert quality_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "25.0"
    assert hass.states.get(zone_entity_id).attributes["measurement_quality"] == "measured"
    assert hass.states.get(installation_entity_id).state == "25.0"
    assert hass.states.get(status_entity_id).state == "idle"
    assert hass.states.get(active_zone_entity_id).state == "unknown"
    assert hass.states.get(last_delivered_entity_id).state == "25.0"
    assert hass.states.get(last_duration_entity_id).state == "0.001"
    assert hass.states.get(quality_entity_id).state == "measured"
    assert operations == [
        ("turn_on", "switch.main"),
        ("turn_on", "switch.zone_lawn"),
        ("turn_off", "switch.zone_lawn"),
        ("turn_off", "switch.main"),
    ]
    assert persisted_zone_at_open == ["zone-1"]


@pytest.mark.parametrize(
    ("stop_service", "emergency_stop"),
    [("stop", False), ("emergency_stop", True)],
)
async def test_stop_actions_close_active_valves_and_account_partial_water(
    hass: HomeAssistant, stop_service: str, emergency_stop: bool
) -> None:
    """Stop an active dose safely and persist an emergency lock when requested."""
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
        was_on = hass.states.get(entity_id).state == STATE_ON
        hass.states.async_set(entity_id, STATE_OFF)
        if entity_id == "switch.zone_lawn" and was_on:
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
    operations.clear()

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
    registry = er.async_get(hass)
    status_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "installation-1_status")
    active_zone_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_active_zone"
    )
    assert status_entity_id is not None
    assert active_zone_entity_id is not None
    assert hass.states.get(status_entity_id).state == "watering"
    assert hass.states.get(active_zone_entity_id).state == "Rasen"
    await hass.services.async_call(
        DOMAIN,
        stop_service,
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    assert zone_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "25.0"
    expected_operations = [
        ("turn_on", "switch.main"),
        ("turn_on", "switch.zone_lawn"),
        ("turn_off", "switch.zone_lawn"),
        ("turn_off", "switch.main"),
    ]
    if emergency_stop:
        expected_operations.extend(
            [
                ("turn_off", "switch.zone_lawn"),
                ("turn_off", "switch.main"),
            ]
        )
    assert operations == expected_operations
    assert (
        await IrrigationStore(hass, entry.entry_id).async_load()
    ).emergency_stop is emergency_stop


async def test_assign_water_moves_unassigned_consumption_to_zone(
    hass: HomeAssistant,
) -> None:
    """Attribute measured water without changing installation consumption."""
    prepare_closed_switches(hass, "switch.zone_lawn")
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
    assert hass.states.get(zone_entity_id).attributes["measurement_quality"] == "unknown"
    assert hass.states.get(installation_entity_id).state == "10.0"
    assert hass.states.get(unassigned_entity_id).state == "6.0"


@pytest.mark.parametrize(
    ("flow_l_min", "error_text", "zone_locked", "installation_locked"),
    [
        (5, "below minimum", True, False),
        (25, "exceeds maximum", False, True),
    ],
)
async def test_flow_fault_stops_and_applies_correct_safety_scope(
    hass: HomeAssistant,
    flow_l_min: float,
    error_text: str,
    zone_locked: bool,
    installation_locked: bool,
) -> None:
    """Persist a zone lock for low flow and installation lock for high flow."""

    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_ON)

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set("switch.zone_lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        str(flow_l_min),
        {ATTR_UNIT_OF_MEASUREMENT: (UnitOfVolumeFlowRate.LITERS_PER_MINUTE)},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
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
                "min_flow": 10,
                "max_flow": 20,
                "flow_grace_seconds": 0,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Rasen",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)

    with pytest.raises(HomeAssistantError, match=error_text):
        await hass.services.async_call(
            DOMAIN,
            "start_manual",
            {
                "config_entry_id": entry.entry_id,
                "zone_subentry_id": subentry.subentry_id,
                "duration": 1,
            },
            blocking=True,
        )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_lock_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "zone-1_safety_lock"
    )
    emergency_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-1_emergency_stop"
    )
    installation_lock_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-1_safety_lock"
    )
    assert zone_lock_entity_id is not None
    assert emergency_entity_id is not None
    assert installation_lock_entity_id is not None
    assert hass.states.get(zone_lock_entity_id).state == (STATE_ON if zone_locked else STATE_OFF)
    assert hass.states.get(installation_lock_entity_id).state == (
        STATE_ON if installation_locked else STATE_OFF
    )
    assert hass.states.get(emergency_entity_id).state == STATE_OFF

    if installation_locked:
        hass.states.async_set(
            "sensor.flow",
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: (UnitOfVolumeFlowRate.LITERS_PER_MINUTE)},
        )
    await hass.services.async_call(
        DOMAIN,
        ("reset_zone_safety" if zone_locked else "reset_installation_safety"),
        (
            {
                "config_entry_id": entry.entry_id,
                "zone_subentry_id": subentry.subentry_id,
            }
            if zone_locked
            else {"config_entry_id": entry.entry_id}
        ),
        blocking=True,
    )
    assert hass.states.get(zone_lock_entity_id).state == STATE_OFF
    assert hass.states.get(installation_lock_entity_id).state == STATE_OFF
    assert hass.states.get(emergency_entity_id).state == STATE_OFF


async def test_emergency_stop_blocks_manual_watering(hass: HomeAssistant) -> None:
    """Never allow a normal manual request to override the safety lock."""
    prepare_closed_switches(hass, "switch.zone_lawn")
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
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    emergency_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-1_emergency_stop"
    )
    assert emergency_entity_id is not None
    assert hass.states.get(emergency_entity_id).state == STATE_ON

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

    await hass.services.async_call(
        DOMAIN,
        "reset_emergency_stop",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )

    assert not (await IrrigationStore(hass, entry.entry_id).async_load()).emergency_stop
    assert hass.states.get(emergency_entity_id).state == STATE_OFF


async def test_setup_recovers_interrupted_execution_from_meter_baseline(
    hass: HomeAssistant,
) -> None:
    """Close valves and account measurable water from an interrupted dose."""
    operations: list[str] = []

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(entity_id)
        hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_ON)
    hass.states.async_set("switch.zone_lawn", STATE_ON)
    hass.states.async_set("switch.zone_new", STATE_OFF)
    hass.states.async_set(
        "sensor.water_meter",
        "1.025",
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
                "zone_valve": "switch.zone_new",
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
            active_execution=ActiveExecutionState(
                zone_id="zone-1",
                zone_valve="switch.zone_lawn",
                main_valve="switch.main",
                meter_raw_baseline_liters=1_000,
                prepared_at="2026-07-21T09:59:59+00:00",
                watering_started_at="2026-07-21T10:00:00+00:00",
                requested_duration_seconds=600,
                estimated_flow_l_min=None,
            )
        )
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    zone_entity_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    installation_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_water_total"
    )
    assert zone_entity_id is not None
    assert installation_entity_id is not None
    assert hass.states.get(zone_entity_id).state == "25.0"
    assert hass.states.get(installation_entity_id).state == "25.0"
    assert operations == ["switch.zone_new", "switch.zone_lawn", "switch.main"]
    assert (await IrrigationStore(hass, entry.entry_id).async_load()).active_execution is None


async def test_persistent_idle_flow_closes_valves_and_sets_installation_lock(
    hass: HomeAssistant,
) -> None:
    """Detect a leak from HA state events and account raw meter consumption."""
    operations: list[str] = []
    persisted_lock_at_close: list[bool] = []
    monitoring_started = False

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(entity_id)
        if monitoring_started:
            stored = await IrrigationStore(hass, entry.entry_id).async_load()
            persisted_lock_at_close.append(stored.installation_safety_lock is not None)
        hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set("switch.zone_lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.water_meter",
        "100",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
    )
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "water_meter": "sensor.water_meter",
            "flow_sensor": "sensor.flow",
            "leak_flow_threshold": 0.5,
            "leak_duration_seconds": 0.01,
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
    operations.clear()
    monitoring_started = True

    hass.states.async_set(
        "sensor.water_meter",
        "100.2",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
    )
    hass.states.async_set(
        "sensor.flow",
        "1",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    lock_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-1_safety_lock"
    )
    emergency_entity_id = registry.async_get_entity_id(
        "binary_sensor", DOMAIN, "installation-1_emergency_stop"
    )
    unassigned_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_unassigned_water_total"
    )
    assert lock_entity_id is not None
    assert emergency_entity_id is not None
    assert unassigned_entity_id is not None
    assert operations == ["switch.zone_lawn", "switch.main"]
    assert persisted_lock_at_close == [True, True]
    assert hass.states.get(lock_entity_id).state == STATE_ON
    assert hass.states.get(emergency_entity_id).state == STATE_OFF
    assert float(hass.states.get(unassigned_entity_id).state) == pytest.approx(0.2)
    assert hass.states.get(unassigned_entity_id).attributes["measurement_origin"] == (
        "cumulative_meter"
    )
    assert hass.states.get(unassigned_entity_id).attributes["measurement_quality"] == "measured"

    with pytest.raises(HomeAssistantError, match="Hazardous idle flow"):
        await hass.services.async_call(
            DOMAIN,
            "reset_installation_safety",
            {"config_entry_id": entry.entry_id},
            blocking=True,
        )

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_short_idle_flow_artifact_is_ignored_and_unload_cancels_monitoring(
    hass: HomeAssistant,
) -> None:
    """Require continuous flow and leave no listener or confirmation task after unload."""
    operations: list[str] = []

    async def turn_off(call) -> None:
        operations.append(call.data["entity_id"])
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
            "leak_duration_seconds": 0.03,
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    operations.clear()

    hass.states.async_set(
        "sensor.flow",
        "1",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.01)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.04)
    assert (
        await IrrigationStore(hass, entry.entry_id).async_load()
    ).installation_safety_lock is None
    assert operations == []

    hass.states.async_set(
        "sensor.flow",
        "1",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await asyncio.sleep(0.04)

    assert (
        await IrrigationStore(hass, entry.entry_id).async_load()
    ).installation_safety_lock is None
    assert operations == []


async def test_idle_leak_integrates_flow_when_no_cumulative_meter_exists(
    hass: HomeAssistant,
) -> None:
    """Publish visibly integrated unassigned consumption without a meter."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
            "leak_duration_seconds": 0.01,
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.02)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unassigned_entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-1_unassigned_water_total"
    )
    assert unassigned_entity_id is not None
    unassigned_state = hass.states.get(unassigned_entity_id)
    assert float(unassigned_state.state) == pytest.approx(0.01, rel=0.5)
    assert unassigned_state.attributes["measurement_origin"] == "flow_sensor"
    assert unassigned_state.attributes["measurement_quality"] == "integrated"


async def test_active_flow_and_short_post_watering_runoff_do_not_lock(
    hass: HomeAssistant,
) -> None:
    """Ignore active watering and restart the full confirmation window after it."""

    async def turn_on(call) -> None:
        entity_id = call.data["entity_id"]
        hass.states.async_set(entity_id, STATE_ON)
        if entity_id == "switch.zone_lawn":
            hass.states.async_set(
                "sensor.flow",
                "1",
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
            )

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.zone_lawn", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "flow_sensor": "sensor.flow",
            "leak_duration_seconds": 0.03,
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
    await asyncio.sleep(0.01)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.04)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert stored.unassigned_total_liters == 0


async def test_unload_awaits_an_already_confirmed_leak_application(
    hass: HomeAssistant,
) -> None:
    """Finish valve closure and accounting once leak confirmation has succeeded."""
    closure_started = asyncio.Event()
    allow_closure = asyncio.Event()
    monitor_armed = False

    async def turn_off(call) -> None:
        if monitor_armed:
            closure_started.set()
            await allow_closure.wait()
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
            "leak_duration_seconds": 0.01,
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    monitor_armed = True

    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await closure_started.wait()
    unload_task = asyncio.create_task(hass.config_entries.async_unload(entry.entry_id))
    await asyncio.sleep(0)

    assert not unload_task.done()
    locked_state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert locked_state.installation_safety_lock is not None

    allow_closure.set()
    assert await unload_task

    completed_state = await IrrigationStore(hass, entry.entry_id).async_load()
    assert completed_state.installation_safety_lock is not None
    assert completed_state.unassigned_total_liters > 0
    assert completed_state.unassigned_measurement_quality == "integrated"


@pytest.mark.parametrize("invalid_state", [STATE_UNAVAILABLE, "not-a-number", "-1", None])
async def test_invalid_flow_breaks_continuous_leak_observation(
    hass: HomeAssistant,
    invalid_state: str | None,
) -> None:
    """Never bridge unavailable, malformed, implausible, or stale flow samples."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
            "flow_max_age_seconds": 0.005 if invalid_state is None else 30,
            "leak_duration_seconds": 0.03,
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.01)
    if invalid_state is not None:
        hass.states.async_set(
            "sensor.flow",
            invalid_state,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
        )
        await asyncio.sleep(0.005)
    else:
        await asyncio.sleep(0.03)
    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.015)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert stored.unassigned_total_liters == 0

    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await hass.async_block_till_done()


async def test_leak_closes_every_valve_when_initial_lock_persistence_fails(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Never let a storage failure skip confirmed-leak hardware safety."""
    operations: list[str] = []

    async def turn_off(call) -> None:
        entity_id = call.data["entity_id"]
        operations.append(entity_id)
        hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    for entity_id in ("switch.zone_lawn", "switch.zone_beds", "switch.main"):
        hass.states.async_set(entity_id, STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung", "main_valve": "switch.main"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    for index, valve in enumerate(("switch.zone_lawn", "switch.zone_beds"), start=1):
        hass.config_entries.async_add_subentry(
            entry,
            ConfigSubentry(
                data=MappingProxyType(
                    {"name": f"Zone {index}", "zone_valve": valve, "default_duration": 600}
                ),
                subentry_id=f"subentry-{index}",
                subentry_type="zone",
                title=f"Zone {index}",
                unique_id=f"zone-{index}",
            ),
        )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    operations.clear()

    manager = hass.data[DOMAIN][entry.entry_id]
    real_save = manager._store.async_save
    save_calls = 0

    async def fail_first_save(state: StoredInstallationState) -> None:
        nonlocal save_calls
        save_calls += 1
        if save_calls == 1:
            raise OSError("storage unavailable")
        await real_save(state)

    monkeypatch.setattr(manager._store, "async_save", fail_first_save)

    with pytest.raises(OSError, match="storage unavailable"):
        await manager._async_apply_idle_flow_lock(flow_l_min=2, integrated_liters=1)

    assert operations == ["switch.zone_lawn", "switch.zone_beds", "switch.main"]
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is not None
    assert stored.unassigned_total_liters == 1


@pytest.mark.parametrize("continuity_break", ["low", "removed"])
async def test_each_flow_event_sample_breaks_continuity(
    hass: HomeAssistant,
    continuity_break: str,
) -> None:
    """Preserve brief low and missing transitions between queued high samples."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.main", STATE_OFF)
    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={
            "name": "Gartenbewässerung",
            "main_valve": "switch.main",
            "flow_sensor": "sensor.flow",
            "leak_duration_seconds": 0.08,
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.03)
    if continuity_break == "removed":
        hass.states.async_remove("sensor.flow")
    else:
        hass.states.async_set(
            "sensor.flow",
            "0",
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
        )
    hass.states.async_set(
        "sensor.flow",
        "60",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await asyncio.sleep(0.06)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.installation_safety_lock is None
    assert stored.unassigned_total_liters == 0

    hass.states.async_set(
        "sensor.flow",
        "0",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
    )
    await hass.async_block_till_done()
