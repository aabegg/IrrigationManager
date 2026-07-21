"""Config-flow behavior tests for Irrigation Manager."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import (
    CONF_FLOW_SENSOR,
    CONF_MAIN_VALVE,
    CONF_WATER_METER,
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
