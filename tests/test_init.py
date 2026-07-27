"""Focused Home Assistant lifecycle and storage tests for version 2."""

from dataclasses import replace
from types import MappingProxyType

import pytest
import voluptuous as vol
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_OFF, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.models import StoredInstallationState
from custom_components.irrigation_manager.services import START_MANUAL_SCHEMA
from custom_components.irrigation_manager.storage import IrrigationStore


@pytest.mark.parametrize(
    "targets",
    [
        {},
        {"duration": 1, "amount": 1},
        {"amount": 1},
        {"duration": 1, "hard_time_limit": 2},
    ],
)
def test_manual_action_requires_exactly_one_complete_target(
    targets: dict[str, float],
) -> None:
    """Reject missing, ambiguous, and incomplete action targets."""
    with pytest.raises(vol.Invalid):
        START_MANUAL_SCHEMA(
            {
                "config_entry_id": "installation-1",
                "zone_subentry_id": "zone-1",
                **targets,
            }
        )


async def test_fresh_store_uses_only_current_v2_schema(hass: HomeAssistant) -> None:
    """Return the compact current schema for a new installation."""
    state = await IrrigationStore(hass, "fresh-v2").async_load()

    assert state == StoredInstallationState()
    assert set(state.as_dict()) == {
        "installation_total_liters",
        "zone_totals_liters",
        "zone_measurement_quality",
        "zone_last_delivered_liters",
        "zone_last_duration_seconds",
        "unassigned_total_liters",
        "unassigned_available_liters",
        "unassigned_measurement_quality",
        "unassigned_measurement_origin",
        "idle_meter_raw_baseline_liters",
        "emergency_stop",
        "installation_safety_lock",
        "installation_safety_lock_at",
        "calibration_proposal",
        "active_execution",
        "manual_requests",
        "irrigation_executions",
        "next_request_sequence",
        "meter_accumulated_liters",
        "meter_last_raw_liters",
        "meter_correction_liters",
        "meter_correction_history",
        "meter_reset_count",
        "meter_source_entity_id",
        "meter_source_liters_per_count",
        "water_consumption_history",
        "water_history_incomplete",
        "operation_enabled",
        "automation_enabled",
        "zone_operation_enabled",
        "zone_automation_enabled",
    }


async def test_store_migrates_shipped_rc6_data_to_v2(hass: HomeAssistant) -> None:
    """Run the Home Assistant Store migration from the shipped rc6 version."""
    await Store[dict[str, object]](
        hass,
        1,
        "irrigation_manager.rc6",
        atomic_writes=True,
        minor_version=29,
    ).async_save(
        {
            "installation_total_liters": 12.0,
            "zone_totals_liters": {"zone-1": 12.0},
            "winter_lock": True,
            "weather_failure_since": "legacy",
        }
    )

    state = await IrrigationStore(hass, "rc6").async_load()

    assert state.installation_total_liters == 12
    assert state.zone_totals_liters == {"zone-1": 12}
    assert "winter_lock" not in state.as_dict()
    assert "weather_failure_since" not in state.as_dict()


async def test_setup_publishes_v2_initial_snapshot_without_legacy_fields(
    hass: HomeAssistant,
) -> None:
    """Initialize the coordinator exclusively from current persisted state."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "none",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-v2",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=MappingProxyType(
                {
                    "name": "Lawn",
                    "zone_valve": "switch.lawn",
                    "control_type": "time",
                    "operation_enabled": True,
                    "automation_enabled": True,
                    "weekly_schedule": [],
                }
            ),
            subentry_id="zone-subentry",
            subentry_type="zone",
            title="Lawn",
            unique_id="zone-v2",
        ),
    )

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    snapshot = entry.runtime_data.coordinator.data
    assert snapshot.status == "idle"
    assert snapshot.operation_enabled is True
    assert snapshot.automation_enabled is True
    assert not hasattr(snapshot, "winter_lock")
    assert not hasattr(snapshot, "zone_safety_locks")
    assert not hasattr(snapshot, "maintenance_active")

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_zone_status_anchor_publishes_live_meter_capability_and_volume_limit(
    hass: HomeAssistant,
) -> None:
    """Integrate configured meter limits with the state consumed by the bundled card."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    hass.states.async_set("sensor.water", "100", {"unit_of_measurement": UnitOfVolume.LITERS})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "cumulative",
            "meter_entity": "sensor.water",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-metered",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "volume",
                "volume_max_runtime": 900,
                "operation_enabled": True,
                "automation_enabled": True,
                "weekly_schedule": [],
            }
        ),
        subentry_id="zone-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-metered",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    anchor_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-metered_zone_status")
    installation_anchor_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-metered_status"
    )
    assert anchor_id is not None
    assert installation_anchor_id is not None
    anchor = hass.states.get(anchor_id)
    installation_anchor = hass.states.get(installation_anchor_id)
    assert anchor is not None
    assert installation_anchor is not None
    assert anchor.attributes["volume_control_available"] is True
    assert anchor.attributes["max_manual_volume_runtime_seconds"] == 900
    assert "max_manual_duration_seconds" not in anchor.attributes
    assert installation_anchor.attributes["volume_control_available"] is True
    assert "physical_meter" in installation_anchor.attributes["card_entities"]

    coordinator = entry.runtime_data.coordinator
    coordinator.set_snapshot(
        replace(
            coordinator.data,
            active_zone_id="zone-metered",
            active_execution_id="execution-1",
        )
    )
    await hass.async_block_till_done()
    active_anchor = hass.states.get(anchor_id)
    assert active_anchor is not None
    assert active_anchor.attributes["active_execution_id"] == "execution-1"

    coordinator.set_snapshot(replace(coordinator.data, active_zone_id="another-zone"))
    await hass.async_block_till_done()
    inactive_anchor = hass.states.get(anchor_id)
    assert inactive_anchor is not None
    assert "active_execution_id" not in inactive_anchor.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_metered_to_unmetered_setup_removes_renamed_meter_entities_by_unique_id(
    hass: HomeAssistant,
) -> None:
    """Retire every meter-only registry entity even after users renamed entity IDs."""

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    hass.states.async_set("sensor.water", "100", {"unit_of_measurement": UnitOfVolume.LITERS})
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "cumulative",
            "meter_entity": "sensor.water",
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-transition",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "time",
                "operation_enabled": True,
                "automation_enabled": True,
                "weekly_schedule": [],
            }
        ),
        subentry_id="zone-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-transition",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    physical_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "installation-transition_physical_meter"
    )
    zone_water_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-transition_water_total")
    assert physical_id is not None
    assert zone_water_id is not None
    registry.async_update_entity(physical_id, new_entity_id="sensor.renamed_physical_meter")
    registry.async_update_entity(zone_water_id, new_entity_id="sensor.renamed_zone_water")

    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_update_entry(
        entry,
        data={
            "name": "Garden",
            "meter_type": "none",
            "operation_enabled": True,
            "automation_enabled": True,
        },
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        registry.async_get_entity_id("sensor", DOMAIN, "installation-transition_physical_meter")
        is None
    )
    assert registry.async_get_entity_id("sensor", DOMAIN, "zone-transition_water_total") is None
    assert registry.async_get("sensor.renamed_physical_meter") is None
    assert registry.async_get("sensor.renamed_zone_water") is None

    assert await hass.config_entries.async_unload(entry.entry_id)
