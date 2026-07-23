"""Config-flow behavior tests for Irrigation Manager."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import STATE_OFF, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.config_flow import ZONE_SCHEMA
from custom_components.irrigation_manager.const import (
    CONF_AUTOMATION_ENABLED,
    CONF_CALIBRATION_SETTLE_SECONDS,
    CONF_FLOW_SENSOR,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_MAIN_VALVE,
    CONF_MAINTENANCE_CONFIRMATION_INTERVAL,
    CONF_MAINTENANCE_MAX_DURATION,
    CONF_METER_FAILURE_STRATEGY,
    CONF_WATER_METER,
    CONF_WATERING_WINDOWS,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)


def test_wind_threshold_selector_uses_canonical_meters_per_second() -> None:
    """Make the stored wind-threshold unit explicit in every zone form."""
    selector = next(
        value for key, value in ZONE_SCHEMA.schema.items() if str(key) == "wind_interlock_threshold"
    )

    assert selector.config["unit_of_measurement"] == UnitOfSpeed.METERS_PER_SECOND


async def test_user_can_create_an_irrigation_installation(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Create one installation from validated HA entity selections."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "create"
    with patch(
        "custom_components.irrigation_manager.config_flow.uuid4",
    ) as uuid4:
        uuid4.return_value.hex = "installation-1"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"name": "Gartenbewässerung", "purpose": "private_garden"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_MAIN_VALVE: "switch.relais_09"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "meter_kind": "cumulative",
                CONF_WATER_METER: ("sensor.wasserzahler_bewasserung_wasserzahler_gesamt"),
                CONF_FLOW_SENSOR: ("sensor.wasserzahler_bewasserung_wasserdurchfluss"),
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "weather_strategy": "local",
                CONF_WEATHER_ENTITY: "weather.forecast_home",
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "installation_max_delivery_runtime": 14_400,
                "hardware_shutoff_acknowledged": True,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm_ready": True}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Gartenbewässerung"
    assert result["result"].unique_id == "installation-1"
    assert result["data"][CONF_MAIN_VALVE] == "switch.relais_09"
    assert result["data"][CONF_LEAK_MONITORING] is True
    assert result["data"][CONF_LEAK_FLOW_THRESHOLD] == 0.5
    assert result["data"][CONF_LEAK_DURATION_SECONDS] == 30
    assert result["data"]["actuator_feedback_max_age_seconds"] == 300
    assert result["data"]["external_failure_policy"] == "fail_safe"


async def test_user_can_add_a_zone_subentry(hass: HomeAssistant) -> None:
    """Add one repeatable irrigation zone below an installation."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Gartenbewässerung",
        data={"name": "Gartenbewässerung"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"setup_mode": "expert"}
    )

    with patch(
        "custom_components.irrigation_manager.config_flow.uuid4",
    ) as uuid4:
        uuid4.return_value.hex = "zone-1"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Rasen",
                "zone_valve": "switch.relais_11",
                "default_duration": 600,
                "min_flow": 5.0,
                "max_flow": 20.0,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert len(entry.subentries) == 1
    subentry = next(iter(entry.subentries.values()))
    assert subentry.title == "Rasen"
    assert subentry.unique_id == "zone-1"
    assert subentry.data["zone_valve"] == "switch.relais_11"
    assert subentry.data[CONF_METER_FAILURE_STRATEGY] == "abort"
    assert subentry.data[CONF_AUTOMATION_ENABLED] is False
    assert subentry.data[CONF_WATERING_WINDOWS] == ["04:00-06:00"]
    assert subentry.data["external_failure_policy"] == "fail_safe"
    assert subentry.data["wind_manual_policy"] == "allow"


async def test_researched_profiles_show_provenance_and_derived_deficit_before_save(
    hass: HomeAssistant,
) -> None:
    """Require confirmation of source uncertainty and the impacted resolved deficit."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden"},
        unique_id="installation-profile-preview",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"setup_mode": "expert"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "default_duration": 600,
            "min_flow": 5,
            "max_flow": 20,
            "plant_profile": "builtin:plant:cool-season-turf:v1",
            "soil_profile": "builtin:soil:sandy-loam:v1",
            "irrigation_profile": "builtin:irrigation:drip:v1",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profile_confirmation"
    preview = result["description_placeholders"]["preview"]
    assert '"resolved_total_available_water_mm": 36.0' in preview
    assert '"resolved_readily_available_water_mm": 14.4' in preview
    assert "fao56-ch8-tables19-22" in preview
    assert '"confidence": "medium"' in preview
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"confirm_profile_selection": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert next(iter(entry.subentries.values())).data["plant_profile"] == (
        "builtin:plant:cool-season-turf:v1"
    )


async def test_portable_import_creates_new_entry_with_zone_subentries(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Use the public config-flow subentry API and fresh stable identities."""
    payload = {
        "schema_version": 1,
        "integration": DOMAIN,
        "installation": {
            "id": "source-installation",
            "config": {
                "name": "Imported garden",
                CONF_MAIN_VALVE: "switch.old_main",
                CONF_AUTOMATION_ENABLED: True,
                "hardware_shutoff_acknowledged": True,
            },
        },
        "zones": [
            {
                "id": "source-zone-lawn",
                "config": {
                    "name": "Lawn",
                    "zone_valve": "switch.old_lawn",
                    "default_duration": 600,
                    "min_flow": 5,
                    "max_flow": 20,
                    "plant_profile": "builtin:plant:cool-season-turf:v1",
                    "soil_profile": "builtin:soil:sandy-loam:v1",
                    "agronomic_values_confirmed": True,
                    CONF_AUTOMATION_ENABLED: True,
                },
            },
            {
                "id": "source-zone-beds",
                "config": {
                    "name": "Beds",
                    "zone_valve": "switch.old_beds",
                    "default_duration": 300,
                    "min_flow": 2,
                    "max_flow": 10,
                },
            },
        ],
    }
    for entity_id in ("switch.new_main", "switch.new_lawn", "switch.new_beds"):
        hass.states.async_set(entity_id, "off")

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.side_effect = [
            type("Id", (), {"hex": "new-installation"})(),
            type("Id", (), {"hex": "new-zone-lawn"})(),
            type("Id", (), {"hex": "new-zone-beds"})(),
        ]
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "import"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "payload": payload,
                "entity_remapping": {
                    "switch.old_main": "switch.new_main",
                    "switch.old_lawn": "switch.new_lawn",
                    "switch.old_beds": "switch.new_beds",
                },
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "import_profile_confirmation"
        assert "cool-season-turf" in result["description_placeholders"]["preview"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm_researched_profiles": True}
        )
        assert result["step_id"] == "import_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm_create": True}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == "new-installation"
    assert entry.data[CONF_MAIN_VALVE] == "switch.new_main"
    assert entry.data[CONF_AUTOMATION_ENABLED] is False
    assert entry.data["hardware_shutoff_acknowledged"] is False
    assert [subentry.title for subentry in entry.subentries.values()] == ["Lawn", "Beds"]
    assert [subentry.unique_id for subentry in entry.subentries.values()] == [
        "new-zone-lawn",
        "new-zone-beds",
    ]
    assert [subentry.data["zone_valve"] for subentry in entry.subentries.values()] == [
        "switch.new_lawn",
        "switch.new_beds",
    ]
    assert next(iter(entry.subentries.values())).data["agronomic_values_confirmed"] is True
    assert all(
        subentry.data[CONF_AUTOMATION_ENABLED] is False for subentry in entry.subentries.values()
    )

    options = await hass.config_entries.options.async_init(entry.entry_id)
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"next_step_id": "guided"}
    )
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"next_step_id": "guided_installation"}
    )
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            "name": "Imported garden",
            "hardware_shutoff_acknowledged": True,
            CONF_AUTOMATION_ENABLED: True,
        },
    )
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["hardware_shutoff_acknowledged"] is True
    assert entry.data[CONF_AUTOMATION_ENABLED] is True


async def test_portable_new_entry_import_rejects_missing_target_entities(
    hass: HomeAssistant,
) -> None:
    """Fail before creating an entry when a remapped actuator is unavailable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "payload": {
                "schema_version": 1,
                "integration": DOMAIN,
                "installation": {"id": "source", "config": {"name": "Import"}},
                "zones": [
                    {
                        "id": "zone",
                        "config": {
                            "name": "Missing",
                            "zone_valve": "switch.does_not_exist",
                            "default_duration": 60,
                            "min_flow": 1,
                            "max_flow": 2,
                        },
                    }
                ],
            }
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_import"


async def test_portable_import_rejects_existing_or_concurrent_actuator_ownership(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Serialize final ownership checks and never leave partial imported entries."""
    for entity_id in ("switch.shared_main", "switch.shared_zone"):
        hass.states.async_set(entity_id, "off")
    payload = {
        "schema_version": 1,
        "integration": DOMAIN,
        "installation": {
            "id": "source",
            "config": {"name": "Imported", CONF_MAIN_VALVE: "switch.shared_main"},
        },
        "zones": [
            {
                "id": "source-zone",
                "config": {
                    "name": "Shared",
                    "zone_valve": "switch.shared_zone",
                    "default_duration": 60,
                    "min_flow": 1,
                    "max_flow": 2,
                },
            }
        ],
    }

    async def preview() -> dict[str, object]:
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "import"}
        )
        return await hass.config_entries.flow.async_configure(
            result["flow_id"], {"payload": payload, "entity_remapping": {}}
        )

    first, second = await asyncio.gather(preview(), preview())
    before = len(hass.config_entries.async_entries(DOMAIN))
    results = await asyncio.gather(
        hass.config_entries.flow.async_configure(first["flow_id"], {"confirm_create": True}),
        hass.config_entries.flow.async_configure(second["flow_id"], {"confirm_create": True}),
    )

    assert sum(result["type"] is FlowResultType.CREATE_ENTRY for result in results) == 1
    assert (
        sum(
            result["type"] is FlowResultType.ABORT and result["reason"] == "actuator_already_owned"
            for result in results
        )
        == 1
    )
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == before + 1
    imported = entries[-1]
    assert len(imported.get_subentries_of_type("zone")) == 1

    hass.states.async_set("switch.other_zone", "off")
    conflicting_payload = {
        **payload,
        "installation": {"id": "other", "config": {"name": "Other"}},
        "zones": [
            {
                "id": "other-zone",
                "config": {
                    **payload["zones"][0]["config"],
                    "name": "Other zone",
                    "zone_valve": "switch.other_zone",
                    "zone_valve_feedback": "switch.shared_main",
                },
            }
        ],
    }
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "import"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"payload": conflicting_payload, "entity_remapping": {}}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "actuator_already_owned"
    assert len(hass.config_entries.async_entries(DOMAIN)) == before + 1


async def test_options_flow_updates_installation_and_zone_expert_settings(
    hass: HomeAssistant,
) -> None:
    """Edit every creation-time expert setting without recreating stable IDs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden"},
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    zone_result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    zone_result = await hass.config_entries.subentries.async_configure(
        zone_result["flow_id"], {"setup_mode": "expert"}
    )
    zone_result = await hass.config_entries.subentries.async_configure(
        zone_result["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "default_duration": 600,
            "min_flow": 5,
            "max_flow": 20,
        },
    )
    subentry = next(iter(entry.subentries.values()))
    original_unique_id = subentry.unique_id

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "expert"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden expert",
            CONF_FLOW_SENSOR: "sensor.flow",
            "notify_entities": ["notify.mobile_app_phone"],
            "hardware_shutoff_acknowledged": True,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Garden expert"
    assert entry.data["notify_entities"] == ["notify.mobile_app_phone"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "expert"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "zone"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"zone_subentry_id": subentry.subentry_id}
    )
    assert result["step_id"] == "zone_settings"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Lawn expert",
            "zone_valve": "switch.lawn",
            "default_duration": 900,
            "min_flow": 6,
            "max_flow": 21,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert subentry.title == "Lawn expert"
    assert subentry.unique_id == original_unique_id
    assert subentry.data["default_duration"] == 900


async def test_profile_change_shows_impacted_zone_before_saving(hass: HomeAssistant) -> None:
    """Require explicit confirmation with an impacted-zone preview."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "hardware_shutoff_acknowledged": True,
            "custom_profiles": {
                "plant:lawn": {
                    "kind": "plant",
                    "values": {"seasonal_kc": [1.0] * 12},
                }
            },
        },
        unique_id="installation-1",
    )
    entry.add_to_hass(hass)
    zone_result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    zone_result = await hass.config_entries.subentries.async_configure(
        zone_result["flow_id"], {"setup_mode": "expert"}
    )
    await hass.config_entries.subentries.async_configure(
        zone_result["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "default_duration": 600,
            "min_flow": 5,
            "max_flow": 20,
            "plant_profile": "plant:lawn",
        },
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "expert"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden",
            "hardware_shutoff_acknowledged": True,
            "custom_profiles": {
                "plant:lawn": {
                    "kind": "plant",
                    "values": {"seasonal_kc": [0.8] * 12},
                }
            },
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "profile_impact"
    assert result["description_placeholders"] == {"zones": "Lawn"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_profile_changes": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_profile_edit_rejects_concurrent_entry_change(hass: HomeAssistant) -> None:
    """Use the form's optimistic hash instead of overwriting a concurrent profile copy."""
    original_profiles = {
        "plant:lawn": {
            "kind": "plant",
            "values": {"seasonal_kc": [1.0] * 12},
        }
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "custom_profiles": original_profiles},
        unique_id="installation-profile-race",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "expert"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden",
            "hardware_shutoff_acknowledged": True,
            "custom_profiles": {
                "plant:lawn": {
                    "kind": "plant",
                    "values": {"seasonal_kc": [0.8] * 12},
                }
            },
        },
    )
    assert result["step_id"] == "profile_impact"
    concurrent_profiles = {
        **original_profiles,
        "plant:concurrent": {
            "kind": "plant",
            "values": {"seasonal_kc": [0.6] * 12},
        },
    }
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "custom_profiles": concurrent_profiles}
    )

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_profile_changes": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "configuration_changed"
    assert entry.data["custom_profiles"] == concurrent_profiles


async def _create_guided_zone(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    name: str,
    valve: str,
    category: str,
    area: dict[str, object],
    raised_bed: dict[str, object] | None,
    profiles: dict[str, object],
    rate: dict[str, object],
    request_automation: bool,
) -> tuple[dict[str, object], object]:
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    for payload in (
        {"setup_mode": "guided"},
        {"name": name, "zone_valve": valve, "zone_category": category},
        area,
    ):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], payload)
    if raised_bed is not None:
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], raised_bed)
    for payload in (
        profiles,
        rate,
        {
            "request_automation": request_automation,
            "watering_mode": "demand",
            "window_start": "04:00:00",
            "window_end": "06:00:00",
        },
        {"use_cycle_soak": True, "max_dose_minutes": 10, "soak_minutes": 20},
        {"automatic_max_minutes": 60, "maximum_target_liters": 500},
    ):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], payload)
    assert result["step_id"] == "zone_review"
    review = result
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"confirm_profile_selection": True}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = next(item for item in entry.subentries.values() if item.title == name)
    return review, subentry


async def test_novice_raised_bed_vegetables_with_drip(hass: HomeAssistant) -> None:
    """Derive a depth-limited raised-bed profile and calibrated automatic readiness."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "hardware_shutoff_acknowledged": True},
        unique_id="guided-raised-bed",
    )
    entry.add_to_hass(hass)

    review, subentry = await _create_guided_zone(
        hass,
        entry,
        name="Vegetables",
        valve="switch.raised_bed",
        category="raised_bed",
        area={"area_method": "rectangle", "length_m": 2.0, "width_m": 1.2},
        raised_bed={
            "usable_depth_cm": 30,
            "soil_answer": "potting_mix",
            "bed_age": "established",
            "organic_rich": "yes",
            "drainage": "normal",
        },
        profiles={
            "plant_choice": "vegetables",
            "irrigation_method": "drip",
            "exposure": "full_sun",
        },
        rate={"rate_source": "measured", "min_flow": 1.8, "max_flow": 2.2},
        request_automation=True,
    )

    preview = review["description_placeholders"]["preview"]
    assert "Usable water storage" in preview
    assert "water available before plant stress" in preview
    assert "TAW" in preview
    assert "RAW" in preview
    assert subentry.data["area_m2"] == 2.4
    assert subentry.data["profile_overrides"]["total_available_water_mm"] == 45.0
    assert subentry.data[CONF_AUTOMATION_ENABLED] is True


async def test_novice_lawn_sprinklers_keep_estimated_rate_uncalibrated(
    hass: HomeAssistant,
) -> None:
    """Use sprinkler defaults and preview runtime without treating an estimate as calibration."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Garden", data={"name": "Garden"}, unique_id="guided-lawn"
    )
    entry.add_to_hass(hass)

    review, subentry = await _create_guided_zone(
        hass,
        entry,
        name="Lawn",
        valve="switch.lawn_guided",
        category="lawn",
        area={"area_method": "measured", "area_m2": 80},
        raised_bed=None,
        profiles={
            "plant_choice": "lawn",
            "soil_answer": "clay_loam",
            "irrigation_method": "rotor",
            "exposure": "full_sun",
        },
        rate={"rate_source": "estimated", "application_rate_mm_h": 12},
        request_automation=True,
    )

    assert "runtime about" in review["description_placeholders"]["preview"]
    assert (
        "blocked until area and measured flow are ready"
        in review["description_placeholders"]["preview"]
    )
    assert subentry.data[CONF_AUTOMATION_ENABLED] is False
    assert "min_flow" not in subentry.data
    assert "max_flow" not in subentry.data
    assert subentry.data["soak_duration"] == 1_200


async def test_unknown_raised_bed_soil_uses_bounded_sand_storage(
    hass: HomeAssistant,
) -> None:
    """Never overstate raised-bed storage when the novice cannot identify the soil mix."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Garden", data={"name": "Garden"}, unique_id="unknown-bed"
    )
    entry.add_to_hass(hass)

    review, subentry = await _create_guided_zone(
        hass,
        entry,
        name="Unknown bed",
        valve="switch.unknown_bed",
        category="raised_bed",
        area={"area_method": "measured", "area_m2": 2},
        raised_bed={
            "usable_depth_cm": 30,
            "soil_answer": "unknown",
            "bed_age": "unknown",
            "organic_rich": "unknown",
            "drainage": "unknown",
        },
        profiles={
            "plant_choice": "vegetables",
            "irrigation_method": "drip",
            "exposure": "partial_sun",
        },
        rate={"rate_source": "unknown"},
        request_automation=False,
    )

    assert subentry.data["soil_profile"] == "builtin:soil:sand:v1"
    assert subentry.data["profile_overrides"]["total_available_water_mm"] == 18.0
    assert subentry.data["profile_overrides"]["readily_available_water_mm"] == 6.3
    assert "Unknown soil conservatively uses sand" in review["description_placeholders"]["preview"]
    assert "no automatic demand reduction" in review["description_placeholders"]["preview"]


async def test_novice_shrubs_accept_unknown_answers_fail_safe(hass: HomeAssistant) -> None:
    """Keep unknown observations explicit and automatic release disabled."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Garden", data={"name": "Garden"}, unique_id="guided-shrubs"
    )
    entry.add_to_hass(hass)

    review, subentry = await _create_guided_zone(
        hass,
        entry,
        name="Hedge",
        valve="switch.hedge_guided",
        category="shrubs",
        area={"area_method": "unknown"},
        raised_bed=None,
        profiles={
            "plant_choice": "shrubs",
            "soil_answer": "unknown",
            "irrigation_method": "drip",
            "exposure": "sheltered",
        },
        rate={"rate_source": "unknown"},
        request_automation=True,
    )

    assert "Area is provisional" in review["description_placeholders"]["preview"]
    assert "Unknown soil conservatively uses sand" in review["description_placeholders"]["preview"]
    assert subentry.data["soil_profile"] == "builtin:soil:sand:v1"
    assert subentry.data[CONF_AUTOMATION_ENABLED] is False


async def test_guided_reconfigure_preserves_expert_only_values(hass: HomeAssistant) -> None:
    """Merge guided changes over stored data instead of replacing hidden expert settings."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Garden", data={"name": "Garden"}, unique_id="guided-edit"
    )
    entry.add_to_hass(hass)
    created = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    created = await hass.config_entries.subentries.async_configure(
        created["flow_id"], {"setup_mode": "expert"}
    )
    await hass.config_entries.subentries.async_configure(
        created["flow_id"],
        {
            "name": "Shrubs",
            "zone_valve": "switch.shrubs",
            "default_duration": 600,
            "min_flow": 2,
            "max_flow": 4,
            "external_block": "binary_sensor.water_ban",
            "zone_priority": 17,
            "profile_overrides": {
                "total_available_water_mm": 999,
                "readily_available_water_mm": 888,
                "effective_root_depth_m": 9,
                "application_efficiency": 0.1,
                "operator_note": "keep",
            },
        },
    )
    subentry = next(iter(entry.subentries.values()))

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_guided"}
    )
    assert result["step_id"] == "zone_basic"
    assert (
        result["data_schema"]({"name": "Shrubs", "zone_valve": "switch.shrubs"})["zone_category"]
        == "raised_bed"
    )
    for payload in (
        {
            "name": "Raised bed guided",
            "zone_valve": "switch.shrubs",
            "zone_category": "raised_bed",
        },
        {"area_method": "measured", "area_m2": 12},
        {
            "usable_depth_cm": 30,
            "soil_answer": "potting_mix",
            "bed_age": "established",
            "organic_rich": "yes",
            "drainage": "normal",
        },
        {
            "plant_choice": "vegetables",
            "irrigation_method": "drip",
            "exposure": "partial_sun",
        },
        {"rate_source": "measured", "min_flow": 2.1, "max_flow": 3.9},
        {
            "request_automation": False,
            "watering_mode": "demand",
            "window_start": "04:00:00",
            "window_end": "06:00:00",
        },
        {"use_cycle_soak": False, "max_dose_minutes": 30, "soak_minutes": 0},
        {"automatic_max_minutes": 60, "maximum_target_liters": 500},
        {"confirm_profile_selection": True},
    ):
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], payload)
    assert result["type"] is FlowResultType.ABORT
    assert subentry.title == "Raised bed guided"
    assert subentry.data["external_block"] == "binary_sensor.water_ban"
    assert subentry.data["zone_priority"] == 17
    assert subentry.data["profile_overrides"] == {
        "operator_note": "keep",
        "total_available_water_mm": 45.0,
        "readily_available_water_mm": 15.75,
    }


async def test_zone_reconfigure_guides_flow_calibration(hass: HomeAssistant) -> None:
    """Run and explicitly accept calibration from the zone subentry settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            CONF_MAINTENANCE_MAX_DURATION: 300,
            CONF_MAINTENANCE_CONFIRMATION_INTERVAL: 30,
            CONF_CALIBRATION_SETTLE_SECONDS: 2,
        },
        unique_id="calibration-flow",
    )
    entry.add_to_hass(hass)
    created = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    created = await hass.config_entries.subentries.async_configure(
        created["flow_id"], {"setup_mode": "expert"}
    )
    await hass.config_entries.subentries.async_configure(
        created["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "default_duration": 600,
            "min_flow": 5,
            "max_flow": 20,
        },
    )
    subentry = next(iter(entry.subentries.values()))
    proposal = {
        "proposal_id": "proposal-1",
        "zone_subentry_id": subentry.subentry_id,
        "status": "pending",
        "average_flow_l_min": 10.0,
        "proposed_min_flow_l_min": 8.0,
        "proposed_max_flow_l_min": 12.0,
        "delivered_liters": 3.3,
        "duration_seconds": 60.0,
        "opening_latency_seconds": 1.0,
        "post_run_liters": 0.2,
    }
    manager = Mock()
    manager.calibration_proposal.side_effect = [None, proposal]
    manager.async_start_maintenance_test = AsyncMock(
        return_value={"test_id": "test-1", "expires_at": "later"}
    )
    manager.is_supervised_test_active.side_effect = [True, False]
    manager.async_confirm_maintenance_test = AsyncMock(
        return_value={"test_id": "test-1", "confirmation_deadline": "later"}
    )
    manager.async_resolve_calibration = AsyncMock(return_value={**proposal, "status": "accepted"})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": subentry.subentry_id},
    )
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == [
        "reconfigure_guided",
        "reconfigure_expert",
        "calibration",
    ]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "calibration"}
    )
    assert result["step_id"] == "calibration"
    duration_selector = next(
        value for key, value in result["data_schema"].schema.items() if str(key) == "duration"
    )
    assert duration_selector.config["max"] >= 60
    assert duration_selector.config["mode"] == "box"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"duration": 60, "confirm_supervision": False}
    )
    assert result["step_id"] == "calibration"
    assert result["errors"] == {"base": "calibration_supervision_required"}
    manager.async_start_maintenance_test.assert_not_awaited()
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"duration": 60, "confirm_supervision": True}
    )
    assert result["step_id"] == "calibration_running"
    manager.async_start_maintenance_test.assert_awaited_once_with(
        zone_subentry_id=subentry.subentry_id,
        duration_seconds=60.0,
        kind="calibration",
    )

    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["step_id"] == "calibration_running"
    assert "renewed" in result["description_placeholders"]["status"]
    manager.async_confirm_maintenance_test.assert_awaited_once_with(test_id="test-1")
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["step_id"] == "calibration_review"
    assert "8.0-12.0 L/min" in result["description_placeholders"]["result"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"resolution": "accept", "confirm_resolution": True}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "calibration_accepted"
    manager.async_resolve_calibration.assert_awaited_once_with(
        proposal_id="proposal-1", resolution="accept"
    )


async def test_novice_runtime_readiness_and_targets_match_guided_preview(
    hass: HomeAssistant,
) -> None:
    """Exercise persisted novice configs through the production automatic planner."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            CONF_AUTOMATION_ENABLED: True,
            "hardware_shutoff_acknowledged": True,
        },
        unique_id="guided-runtime",
        version=1,
        minor_version=7,
    )
    entry.add_to_hass(hass)
    _, raised = await _create_guided_zone(
        hass,
        entry,
        name="Runtime vegetables",
        valve="switch.runtime_bed",
        category="raised_bed",
        area={"area_method": "measured", "area_m2": 2.4},
        raised_bed={
            "usable_depth_cm": 30,
            "soil_answer": "potting_mix",
            "bed_age": "established",
            "organic_rich": "yes",
            "drainage": "normal",
        },
        profiles={
            "plant_choice": "vegetables",
            "irrigation_method": "drip",
            "exposure": "full_sun",
        },
        rate={"rate_source": "measured", "min_flow": 1.8, "max_flow": 2.2},
        request_automation=True,
    )
    _, lawn = await _create_guided_zone(
        hass,
        entry,
        name="Runtime lawn",
        valve="switch.runtime_lawn",
        category="lawn",
        area={"area_method": "measured", "area_m2": 80},
        raised_bed=None,
        profiles={
            "plant_choice": "lawn",
            "soil_answer": "clay_loam",
            "irrigation_method": "rotor",
            "exposure": "full_sun",
        },
        rate={"rate_source": "estimated", "application_rate_mm_h": 12},
        request_automation=True,
    )

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.runtime_bed", STATE_OFF)
    hass.states.async_set("switch.runtime_lawn", STATE_OFF)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager
    for task in (manager._dispatcher_task, manager._automatic_planner_task):
        if task is not None:
            task.cancel()
    await asyncio.gather(
        *(task for task in (manager._dispatcher_task, manager._automatic_planner_task) if task),
        return_exceptions=True,
    )
    manager._dispatcher_task = None
    manager._automatic_planner_task = None
    assert manager._stored_state.installation_safety_lock is None
    assert manager._stored_state.zone_safety_locks == {}
    now = datetime(2026, 7, 22, 4, 30, tzinfo=UTC)
    manager._stored_state = replace(
        manager._stored_state,
        zone_deficit_mm={raised.unique_id: 15.75, lawn.unique_id: 18.0},
        zone_last_effective_irrigation={
            raised.unique_id: (now - timedelta(days=2)).isoformat(),
            lawn.unique_id: (now - timedelta(days=2)).isoformat(),
        },
    )

    report = await manager.async_plan_automatic(dry_run=True, now=now)
    decisions = {item["zone_id"]: item for item in report["zones"]}

    assert decisions[raised.unique_id]["reason"] == "planned"
    assert decisions[raised.unique_id]["target_liters"] == pytest.approx(42.0)
    assert decisions[lawn.unique_id]["reason"] == "automation_disabled"
    assert all(
        lawn.unique_id not in request_id for request_id in report["would_create_request_ids"]
    )
