"""Config-flow behavior tests for Irrigation Manager."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

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


async def test_user_can_create_an_irrigation_installation(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Create one installation from validated HA entity selections."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

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
