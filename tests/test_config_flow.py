"""Config-flow behavior tests for Irrigation Manager."""

import asyncio
from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.config_flow import ZONE_SCHEMA
from custom_components.irrigation_manager.const import (
    CONF_AUTOMATION_ENABLED,
    CONF_FLOW_SENSOR,
    CONF_LEAK_DURATION_SECONDS,
    CONF_LEAK_FLOW_THRESHOLD,
    CONF_LEAK_MONITORING,
    CONF_MAIN_VALVE,
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
            {
                "name": "Gartenbewässerung",
                CONF_MAIN_VALVE: "switch.relais_09",
                CONF_WATER_METER: ("sensor.wasserzahler_bewasserung_wasserzahler_gesamt"),
                CONF_FLOW_SENSOR: ("sensor.wasserzahler_bewasserung_wasserdurchfluss"),
                CONF_WEATHER_ENTITY: "weather.forecast_home",
            },
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
            "config": {"name": "Imported garden", CONF_MAIN_VALVE: "switch.old_main"},
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
        assert result["step_id"] == "import_confirm"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"confirm_create": True}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id == "new-installation"
    assert entry.data[CONF_MAIN_VALVE] == "switch.new_main"
    assert [subentry.title for subentry in entry.subentries.values()] == ["Lawn", "Beds"]
    assert [subentry.unique_id for subentry in entry.subentries.values()] == [
        "new-zone-lawn",
        "new-zone-beds",
    ]
    assert [subentry.data["zone_valve"] for subentry in entry.subentries.values()] == [
        "switch.new_lawn",
        "switch.new_beds",
    ]


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
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden expert",
            CONF_FLOW_SENSOR: "sensor.flow",
            "notify_entities": ["notify.mobile_app_phone"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Garden expert"
    assert entry.data["notify_entities"] == ["notify.mobile_app_phone"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
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
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden",
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
        result["flow_id"], {"next_step_id": "installation"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Garden",
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
