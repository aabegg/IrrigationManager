"""Version 2 config-flow behavior tests for Irrigation Manager."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.config_flow import IrrigationManagerConfigFlow
from custom_components.irrigation_manager.const import DOMAIN, WEEKDAYS


async def _create_v2_entry(hass: HomeAssistant, *, meter_type: str = "none") -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": meter_type,
            "meter_entity": "sensor.water" if meter_type != "none" else None,
            "operation_enabled": True,
            "automation_enabled": True,
        },
        unique_id="installation-1",
        version=2,
    )
    entry.add_to_hass(hass)
    return entry


def _snapshot(**overrides: object) -> SimpleNamespace:
    values = {
        "operation_enabled": True,
        "automation_enabled": True,
        "installation_safety_lock": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def _open_installation_releases(hass: HomeAssistant, entry: MockConfigEntry):
    result = await hass.config_entries.options.async_init(entry.entry_id)
    return await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )


async def test_creation_wizard_creates_first_zone_and_seven_day_schedule(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Create one canonical v2 installation through the only creation path."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["menu_options"] == ["create"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.side_effect = [
            type("Id", (), {"hex": "installation-1"})(),
            type("Id", (), {"hex": "zone-1"})(),
        ]
        for payload, expected_step in (
            ({"name": "Garden"}, "installation_hardware"),
            ({"main_valve": "switch.main"}, "installation_meter"),
            ({"meter_type": "cumulative"}, "installation_meter_details"),
            ({"meter_entity": "sensor.water"}, "installation_extensions"),
            ({"plant_site_module_enabled": False}, "installation_zone"),
            (
                {"name": "Lawn", "zone_valve": "switch.lawn", "control_type": "time"},
                "installation_baseline",
            ),
            (
                {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}},
                "installation_schedule",
            ),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)
            assert result["step_id"] == expected_step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "monday": {
                    "start": "22:00:00",
                    "end": "00:30:00",
                },
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].version == 2
    assert result["result"].minor_version == IrrigationManagerConfigFlow.MINOR_VERSION == 3
    assert result["data"] == {
        "name": "Garden",
        "operation_enabled": True,
        "automation_enabled": True,
        "main_valve": "switch.main",
        "meter_type": "cumulative",
        "meter_entity": "sensor.water",
        "plant_site_module_enabled": False,
        "seasonal_module_enabled": False,
        "weather_module_enabled": False,
        "soak_module_enabled": False,
    }
    zone = next(iter(result["result"].subentries.values()))
    assert len(zone.data["weekly_schedule"]) == 7
    assert zone.data["base_target"] == 600
    assert zone.data["weekly_schedule"][0]["target"] is None


async def test_home_assistant_migrates_rc19_entry_without_changing_behavior(
    hass: HomeAssistant,
) -> None:
    """Run the public HA migration path and preserve existing irrigation behavior."""
    schedule = [
        {
            "weekday": weekday,
            "start": "04:00:00" if weekday == "monday" else None,
            "end": "05:00:00" if weekday == "monday" else None,
            "target": 600.0 if weekday == "monday" else None,
        }
        for weekday in WEEKDAYS
    ]
    expected_schedule = deepcopy(schedule)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "none",
            "operation_enabled": True,
            "automation_enabled": True,
            "plant_site_module_enabled": False,
            "seasonal_module_enabled": False,
            "weather_module_enabled": False,
            "soak_module_enabled": False,
        },
        unique_id="irrigation-rc19-migration",
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
            "operation_enabled": True,
            "automation_enabled": True,
            "base_target": 600.0,
            "weekly_schedule": schedule,
            "use_plant_site_model": False,
            "subareas": [],
        },
        subentry_id="zone-rc19-migration",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-rc19-migration",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await entry.async_migrate(hass)

    assert entry.minor_version == 3
    assert entry.data["operation_enabled"] is True
    assert entry.data["automation_enabled"] is True
    migrated = entry.subentries[zone.subentry_id].data
    assert migrated["operation_enabled"] is True
    assert migrated["automation_enabled"] is True
    assert migrated["base_target"] == 600.0
    assert migrated["weekly_schedule"] == expected_schedule
    assert migrated["use_seasonal_adjustment"] is False
    assert migrated["seasonal_factors"] == {
        month: 1.0
        for month in (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    }


async def test_creation_collects_and_confirms_seasonal_curve_before_schedule(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Expose the completed module and persist its curve only after preview confirmation."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    for payload in (
        {"name": "Garden"},
        {},
        {"meter_type": "none"},
        {"plant_site_module_enabled": False, "seasonal_module_enabled": True},
        {"name": "Lawn", "zone_valve": "switch.lawn", "control_type": "time"},
        {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}},
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)
    assert result["step_id"] == "first_zone_seasonal"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_seasonal_adjustment": True}
    )
    assert result["step_id"] == "first_zone_seasonal_curve"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"january": 1.5})
    assert result["step_id"] == "first_zone_seasonal_review"
    assert "00:15:00" in result["description_placeholders"]["preview"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"confirm_seasonal_curve": True}
    )
    assert result["step_id"] == "installation_schedule"

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.side_effect = [
            type("Id", (), {"hex": "irrigation-seasonal"})(),
            type("Id", (), {"hex": "zone-seasonal"})(),
        ]
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    zone = next(iter(result["result"].subentries.values()))
    assert result["data"]["seasonal_module_enabled"] is True
    assert zone.data["use_seasonal_adjustment"] is True
    assert zone.data["seasonal_factors"]["january"] == 1.5
    assert zone.data["seasonal_factors"]["february"] == 1.0


async def test_creation_validates_pulse_factor_and_complete_schedule_rows(
    hass: HomeAssistant,
) -> None:
    """Require pulse conversion and complete non-overlapping weekday rows."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Garden"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"meter_type": "pulse"}
    )
    assert result["step_id"] == "installation_meter_details"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"meter_entity": "sensor.pulses"}
    )
    assert result["errors"] == {"base": "raw_meter_requires_factor"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "meter_entity": "sensor.pulses",
            "pulse_factor_mode": "pulses_per_liter",
            "pulse_factor": 4,
        },
    )
    assert result["step_id"] == "installation_extensions"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"plant_site_module_enabled": False}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "volume",
            "volume_max_runtime": {"hours": 0, "minutes": 15, "seconds": 0},
        },
    )
    assert result["step_id"] == "installation_baseline"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"base_target": 10})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monday": {"start": "04:00:00", "target": 10}}
    )
    assert result["errors"] == {"base": "schedule_row_incomplete"}


async def test_meter_wizard_only_asks_fields_relevant_to_selected_type(
    hass: HomeAssistant,
) -> None:
    """Keep cumulative setup free of pulse-only conversion inputs."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Garden"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert {str(key) for key in result["data_schema"].schema} == {"meter_type"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"meter_type": "cumulative"}
    )
    assert {str(key) for key in result["data_schema"].schema} == {"meter_entity"}


async def test_plant_module_collects_subarea_and_keeps_baseline_explicit(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Collect qualitative profile data without deriving the confirmed baseline."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Garden"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"plant_site_module_enabled": True}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"name": "Beds", "zone_valve": "switch.beds", "control_type": "time"},
    )
    assert result["step_id"] == "installation_zone_plant"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"use_plant_site_model": True}
    )

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.side_effect = [
            type("Id", (), {"hex": "subarea-1"})(),
            type("Id", (), {"hex": "installation-1"})(),
            type("Id", (), {"hex": "zone-1"})(),
        ]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "Sunny bed",
                "area_m2": 12,
                "plant_profile": "perennials",
                "development_stage": "established",
                "exposure": "sunny",
                "soil_profile": "loamy",
                "application_profile": "dripline",
                "advanced": {"mulched": True},
                "add_another": False,
            },
        )
        assert result["step_id"] == "installation_baseline"
        assert "Quality: high" in result["description_placeholders"]["recommendation"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"base_target": {"hours": 0, "minutes": 20, "seconds": 0}},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "monday": {
                    "start": "05:00:00",
                    "end": "06:00:00",
                    "target": {"hours": 0, "minutes": 30, "seconds": 0},
                }
            },
        )

    zone = next(iter(result["result"].subentries.values()))
    assert zone.data["base_target"] == 1200
    assert zone.data["weekly_schedule"][0]["target"] == 1800
    assert zone.data["subareas"] == [
        {
            "id": "subarea-1",
            "name": "Sunny bed",
            "area_m2": 12.0,
            "plant_profile": "perennials",
            "development_stage": "established",
            "exposure": "sunny",
            "soil_profile": "loamy",
            "application_profile": "dripline",
            "mulched": True,
        }
    ]


async def test_disabling_plant_module_preserves_zone_profiles(hass: HomeAssistant) -> None:
    """Keep profile configuration dormant while the installation module is disabled."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "plant_site_module_enabled": True}
    )
    zone = ConfigSubentry(
        data={
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "time",
            "base_target": 600,
            "use_plant_site_model": True,
            "subareas": [{"id": "subarea-1", "name": "Beds"}],
            "weekly_schedule": [],
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Beds",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "extensions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"plant_site_module_enabled": False}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["plant_site_module_enabled"] is False
    assert entry.subentries[zone.subentry_id].data["use_plant_site_model"] is True
    assert entry.subentries[zone.subentry_id].data["subareas"] == [
        {"id": "subarea-1", "name": "Beds"}
    ]


async def test_disabling_seasonal_module_preserves_zone_curve(hass: HomeAssistant) -> None:
    """Keep a confirmed curve dormant while the seasonal module is disabled."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "plant_site_module_enabled": False,
            "seasonal_module_enabled": True,
        },
    )
    curve = {
        month: 1.0
        for month in (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    }
    curve["july"] = 1.4
    zone = ConfigSubentry(
        data={
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "time",
            "use_seasonal_adjustment": True,
            "seasonal_factors": curve,
            "weekly_schedule": [],
        },
        subentry_id="zone-seasonal-dormant",
        subentry_type="zone",
        title="Beds",
        unique_id="zone-seasonal-dormant",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "extensions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"plant_site_module_enabled": False, "seasonal_module_enabled": False},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["seasonal_module_enabled"] is False
    assert entry.subentries[zone.subentry_id].data["use_seasonal_adjustment"] is True
    assert entry.subentries[zone.subentry_id].data["seasonal_factors"] == curve


async def test_zone_profile_disable_and_reenable_preserves_subareas(
    hass: HomeAssistant,
) -> None:
    """Re-enable dormant zone profiles unless replacement was explicitly requested."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "plant_site_module_enabled": True}
    )
    subareas = [{"id": "subarea-1", "name": "Beds"}]
    zone = ConfigSubentry(
        data={
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "time",
            "base_target": 600,
            "use_plant_site_model": True,
            "subareas": subareas,
            "weekly_schedule": [],
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Beds",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_plant"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"use_plant_site_model": False, "replace_subareas": False}
    )
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[zone.subentry_id].data["subareas"] == subareas

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_plant"}
    )
    assert {str(key) for key in result["data_schema"].schema} == {
        "use_plant_site_model",
        "replace_subareas",
    }
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"use_plant_site_model": True, "replace_subareas": False}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_plant_review"
    assert "Reasons:" in result["description_placeholders"]["recommendation"]
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[zone.subentry_id].data["use_plant_site_model"] is True
    assert entry.subentries[zone.subentry_id].data["subareas"] == subareas


async def test_zone_seasonal_curve_requires_preview_confirmation_before_save(
    hass: HomeAssistant,
) -> None:
    """Configure a complete curve through native selectors and confirm its target preview."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "seasonal_module_enabled": True}
    )
    zone = ConfigSubentry(
        data={
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "time",
            "base_target": 600.0,
            "use_seasonal_adjustment": False,
            "seasonal_factors": {
                month: 1.0
                for month in (
                    "january",
                    "february",
                    "march",
                    "april",
                    "may",
                    "june",
                    "july",
                    "august",
                    "september",
                    "october",
                    "november",
                    "december",
                )
            },
            "weekly_schedule": [],
        },
        subentry_id="zone-seasonal",
        subentry_type="zone",
        title="Beds",
        unique_id="zone-seasonal",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    assert "reconfigure_seasonal" in result["menu_options"]
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_seasonal"}
    )
    assert result["step_id"] == "reconfigure_seasonal"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"use_seasonal_adjustment": True}
    )
    assert result["step_id"] == "reconfigure_seasonal_curve"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"january": 1.5}
    )
    assert result["step_id"] == "reconfigure_seasonal_review"
    assert "00:15:00" in result["description_placeholders"]["preview"]

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"confirm_seasonal_curve": False}
    )
    assert result["errors"] == {"base": "seasonal_confirmation_required"}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"confirm_seasonal_curve": True}
    )

    assert result["type"] is FlowResultType.ABORT
    stored = entry.subentries[zone.subentry_id].data
    assert stored["use_seasonal_adjustment"] is True
    assert stored["seasonal_factors"]["january"] == 1.5
    assert stored["seasonal_factors"]["february"] == 1.0


async def test_baseline_reconfiguration_rejects_existing_window_that_no_longer_fits(
    hass: HomeAssistant,
) -> None:
    """Keep baseline and schedule atomic when a shared target exceeds a window."""
    entry = await _create_v2_entry(hass)
    zone = ConfigSubentry(
        data={
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "time",
            "base_target": 600,
            "weekly_schedule": [
                {
                    "weekday": "monday",
                    "start": "04:00:00",
                    "end": "04:10:00",
                    "target": None,
                }
            ],
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Beds",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_baseline"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"base_target": {"hours": 0, "minutes": 20, "seconds": 0}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "schedule_target_does_not_fit"}
    assert entry.subentries[zone.subentry_id].data["base_target"] == 600


async def test_manual_only_zone_can_be_created_without_baseline(
    hass: HomeAssistant,
) -> None:
    """A zone needs a baseline only when it receives an automatic window."""
    entry = await _create_v2_entry(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Manual", "zone_valve": "switch.manual", "control_type": "time"},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["step_id"] == "minimal_schedule"

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.return_value.hex = "manual-zone"
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = next(iter(entry.subentries.values()))
    assert "base_target" not in zone.data
    assert all(row["start"] is None for row in zone.data["weekly_schedule"])


async def test_new_zone_can_opt_into_available_seasonal_module(
    hass: HomeAssistant,
) -> None:
    """Apply the same confirmed seasonal flow to repeatable zone creation."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "seasonal_module_enabled": True}
    )
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Beds", "zone_valve": "switch.beds", "control_type": "time"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"base_target": {"hours": 0, "minutes": 5, "seconds": 0}}
    )
    assert result["step_id"] == "seasonal"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"use_seasonal_adjustment": True}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"july": 1.4})
    assert result["step_id"] == "seasonal_review"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"confirm_seasonal_curve": True}
    )
    assert result["step_id"] == "minimal_schedule"

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.return_value.hex = "zone-seasonal-new"
        result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = next(iter(entry.subentries.values()))
    assert zone.data["use_seasonal_adjustment"] is True
    assert zone.data["seasonal_factors"]["july"] == 1.4


async def test_automatic_window_requires_baseline(hass: HomeAssistant) -> None:
    """Reject an automatic window until the zone has a confirmed common baseline."""
    entry = await _create_v2_entry(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Automatic", "zone_valve": "switch.auto", "control_type": "time"},
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"monday": {"start": "04:00:00", "end": "05:00:00"}},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "schedule_baseline_required"}


async def test_zone_add_and_reconfigure_expose_only_v2_sections(hass: HomeAssistant) -> None:
    """Add and edit a zone without any guided, expert, profile, or safety path."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "minimal"
    assert result["last_step"] is False
    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.return_value.hex = "zone-1"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "volume",
                "volume_max_runtime": {"hours": 0, "minutes": 20, "seconds": 0},
            },
        )
        assert result["step_id"] == "baseline"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"base_target": 25}
        )
        assert result["step_id"] == "minimal_schedule"
        assert result["last_step"] is True
        assert [str(key) for key in result["data_schema"].schema] == list(WEEKDAYS)
        for day_schema in result["data_schema"].schema.values():
            assert isinstance(day_schema, section)
            assert {str(key) for key in day_schema.schema.schema} == {
                "start",
                "end",
                "target",
            }
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "friday": {"start": "05:00:00", "end": "06:00:00"},
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    zone = next(iter(entry.subentries.values()))
    assert zone.data["volume_max_runtime"] == 1_200
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    assert result["menu_options"] == [
        "reconfigure_minimal",
        "reconfigure_baseline",
        "reconfigure_schedule",
        "releases",
        "calibration",
    ]


async def test_installation_configuration_areas_are_directly_editable(
    hass: HomeAssistant,
) -> None:
    """Edit basis, main valve, and water measurement without unrelated steps."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"] == [
        "configuration_basics",
        "configuration_main_valve_only",
        "configuration_meter_only",
        "extensions",
        "releases",
        "replan",
        "physical_meter_correction",
    ]
    assert result["description_placeholders"] is None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert result["menu_options"] == ["deactivate_installation", "disable_automatic"]
    assert set(result["description_placeholders"]) == {
        "installation_status",
        "automatic_status",
    }

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_basics"}
    )
    assert result["step_id"] == "configuration_basics"
    assert result["last_step"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Back garden"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Back garden"
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_main_valve_only"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"main_valve": "switch.main"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_meter_only"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "pulse"}
    )
    assert result["step_id"] == "configuration_meter_only_details"
    assert result["last_step"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "meter_entity": "sensor.pulses",
            "pulse_factor_mode": "pulses_per_liter",
            "pulse_factor": 4,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Back garden"
    assert entry.data["main_valve"] == "switch.main"
    assert entry.data["meter_type"] == "pulse"
    assert entry.data["meter_entity"] == "sensor.pulses"
    assert entry.data["liters_per_pulse"] == 0.25
    assert "needs_reconfiguration" not in entry.data


async def test_configuration_is_prominent_during_required_reconfiguration(
    hass: HomeAssistant,
) -> None:
    """Keep configuration first while activation remains available with an explanation."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "operation_enabled": False,
            "automation_enabled": False,
            "needs_reconfiguration": True,
        },
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"][0] == "configuration"
    assert "releases" in result["menu_options"]
    assert "activate_installation" not in result["menu_options"]
    assert "enable_automatic" not in result["menu_options"]
    releases = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert releases["menu_options"] == ["activate_installation", "enable_automatic"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Reconfigured"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert entry.data["needs_reconfiguration"] is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "needs_reconfiguration" not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert result["menu_options"] == ["activate_installation", "enable_automatic"]


async def test_meter_cannot_be_removed_from_volume_controlled_installation(
    hass: HomeAssistant,
) -> None:
    """Require explicit zone conversion before removing water measurement."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "volume",
                "volume_max_runtime": 900,
                "weekly_schedule": [],
            },
            subentry_id="zone-1",
            subentry_type="zone",
            title="Lawn",
            unique_id="zone-1",
        ),
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_meter_only"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )
    assert result["errors"] == {"base": "meter_required_by_volume_zones"}


async def test_zone_reconfigure_preserves_calibration_and_removes_only_invalid_volume_limit(
    hass: HomeAssistant,
) -> None:
    """Merge minimal edits into calibrated zone data and clean a time-only field."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "volume",
            "volume_max_runtime": 900,
            "operation_enabled": True,
            "automation_enabled": True,
            "weekly_schedule": [],
            "expected_flow_l_min": 12.5,
            "min_flow": 10.0,
            "max_flow": 15.0,
            "flow_calibrated_at": "2026-07-25T10:00:00+00:00",
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_minimal"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Lawn", "zone_valve": "switch.lawn", "control_type": "time"},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}}
    )
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    reason = result["reason"]
    translations = json.loads(
        (
            Path(__file__).parents[1]
            / "custom_components"
            / "irrigation_manager"
            / "translations"
            / "de.json"
        ).read_text(encoding="utf-8")
    )
    assert translations["config_subentries"]["zone"]["abort"][reason] == (
        "Die Bewässerungszone wurde erfolgreich gespeichert."
    )
    updated = entry.subentries[zone.subentry_id].data
    assert updated["expected_flow_l_min"] == 12.5
    assert updated["min_flow"] == 10.0
    assert updated["max_flow"] == 15.0
    assert updated["flow_calibrated_at"] == "2026-07-25T10:00:00+00:00"
    assert "volume_max_runtime" not in updated


async def test_calibrated_flow_allows_volume_target_to_fit_by_expected_duration(
    hass: HomeAssistant,
) -> None:
    """Validate a volume window against calibrated delivery time, not the hard limit."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "volume",
            "volume_max_runtime": 3600,
            "weekly_schedule": [],
            "expected_flow_l_min": 10.0,
            "flow_calibrated_at": "2026-07-25T10:00:00+00:00",
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_minimal"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "volume",
            "volume_max_runtime": {"hours": 1, "minutes": 0, "seconds": 0},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_baseline"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"base_target": 50}
    )
    assert result["type"] is FlowResultType.ABORT
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_schedule"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"monday": {"start": "04:00:00", "end": "04:15:00", "target": 100}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[zone.subentry_id].data["weekly_schedule"][0]["target"] == 100.0


async def test_calibration_form_converts_structured_duration_to_seconds(
    hass: HomeAssistant,
) -> None:
    """Keep calibration input structured while passing numeric seconds to the runtime."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
            "weekly_schedule": [],
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    manager = SimpleNamespace(
        calibration_proposal=Mock(return_value=None),
        async_start_calibration=AsyncMock(return_value={"test_id": "calibration-1"}),
        is_calibration_active=Mock(return_value=True),
        async_confirm_calibration=AsyncMock(),
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "calibration"}
    )
    duration_marker = next(
        marker for marker in result["data_schema"].schema if str(marker) == "duration"
    )
    assert duration_marker.default() == {"hours": 0, "minutes": 1, "seconds": 0}

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "duration": {"hours": 0, "minutes": 2, "seconds": 3},
            "confirm_supervision": True,
        },
    )

    manager.async_start_calibration.assert_awaited_once_with(
        zone_subentry_id=zone.subentry_id, duration_seconds=123
    )
    assert result["step_id"] == "calibration_running"


async def test_zone_release_menu_tracks_independent_zone_states(
    hass: HomeAssistant,
) -> None:
    """Expose the same state-dependent actions for zones as for the installation."""
    entry = await _create_v2_entry(hass)
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
            "weekly_schedule": [],
        },
        subentry_id="zone-1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    manager = Mock()
    manager.snapshot.return_value = SimpleNamespace(
        zone_operation_enabled={"zone-1": False},
        zone_automation_enabled={"zone-1": True},
    )
    manager.async_set_zone_operation = AsyncMock(return_value={})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert result["menu_options"] == ["activate_zone", "disable_zone_automatic"]
    assert result["description_placeholders"] == {
        "zone_status": "Disabled",
        "automatic_status": "Enabled",
    }

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "activate_zone"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zone_activated"
    manager.async_set_zone_operation.assert_awaited_once_with(
        zone_subentry_id=zone.subentry_id, enabled=True
    )


async def test_installation_actions_and_physical_meter_correction_use_manager(
    hass: HomeAssistant,
) -> None:
    """Run one manager command per action and expose only human-readable results."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    manager = Mock()
    manager.snapshot.return_value = _snapshot()
    manager.automatic_execution_active.return_value = False
    manager.async_set_installation_operation = AsyncMock(return_value={"operation_enabled": False})
    manager.async_set_installation_automation = AsyncMock(
        return_value={"automation_enabled": False}
    )
    manager.async_correct_physical_meter = AsyncMock(
        return_value={"new_total_liters": 1234.5, "difference_liters": 4.5}
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await _open_installation_releases(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "disable_automatic"}
    )
    assert result["step_id"] == "action_result"
    assert "automation_enabled" not in result["description_placeholders"]["result"]
    manager.async_set_installation_automation.assert_awaited_once_with(
        enabled=False, stop_active=False
    )
    manager.async_set_installation_operation.assert_not_awaited()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "physical_meter_correction"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"physical_total_liters": 1234.5, "reason": "Physical reading"}
    )
    assert result["step_id"] == "action_result"
    manager.async_correct_physical_meter.assert_awaited_once_with(
        physical_total_liters=1234.5,
        reason="Physical reading",
    )
    assert result["description_placeholders"]["result"] == (
        "Meter total corrected to 1234.5 L (change 4.5 L)."
    )


async def test_init_menu_tracks_release_and_safety_state(hass: HomeAssistant) -> None:
    """Offer only actions that can change the current runtime state."""
    entry = await _create_v2_entry(hass)
    manager = Mock()
    manager.snapshot.return_value = _snapshot(
        operation_enabled=False,
        automation_enabled=False,
        installation_safety_lock="Leak detected",
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["menu_options"] == [
        "configuration_basics",
        "configuration_main_valve_only",
        "configuration_meter_only",
        "extensions",
        "releases",
        "replan",
        "reset_safety",
    ]
    assert result["description_placeholders"] is None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert result["menu_options"] == ["activate_installation", "enable_automatic"]
    assert result["description_placeholders"] == {
        "installation_status": "Safety lock",
        "automatic_status": "Disabled",
    }


async def test_replan_returns_localized_summary_without_emergency_stop_setting(
    hass: HomeAssistant,
) -> None:
    """Summarize action outcomes without JSON or internal response keys."""
    entry = await _create_v2_entry(hass)
    manager = Mock()
    manager.snapshot.return_value = _snapshot()
    manager.async_plan_automatic = AsyncMock(
        return_value={"created": 3, "replaced": 2, "removed": 1, "horizon_days": 14}
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "emergency_stop" not in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "replan"}
    )
    assert result["description_placeholders"]["result"] == (
        "Replanning completed: 3 created, 2 replaced, 1 removed."
    )
    manager.async_plan_automatic.assert_awaited_once_with()


async def test_activation_and_lock_reset_call_only_the_selected_manager_action(
    hass: HomeAssistant,
) -> None:
    """Keep activation, automatic release, and safety reset as separate actions."""
    entry = await _create_v2_entry(hass)
    manager = Mock()
    manager.snapshot.return_value = _snapshot(operation_enabled=False, automation_enabled=False)
    manager.async_set_installation_operation = AsyncMock(return_value={})
    manager.async_set_installation_automation = AsyncMock(return_value={})
    manager.async_reset_safety_lock = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await _open_installation_releases(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "activate_installation"}
    )
    manager.async_set_installation_operation.assert_awaited_once_with(enabled=True)
    manager.async_set_installation_automation.assert_not_awaited()

    result = await _open_installation_releases(hass, entry)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "enable_automatic"}
    )
    manager.async_set_installation_automation.assert_awaited_once_with(
        enabled=True, stop_active=False
    )

    manager.snapshot.return_value = _snapshot(installation_safety_lock="Leak")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset_safety"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_reset": True}
    )
    manager.async_reset_safety_lock.assert_awaited_once_with()
    assert "reset" in result["description_placeholders"]["result"]


async def test_installation_activation_explains_required_reconfiguration(
    hass: HomeAssistant,
) -> None:
    """Explain the stable configuration condition before calling the manager."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data={"name": "Lawn", "needs_reconfiguration": True},
            subentry_id="zone-1",
            subentry_type="zone",
            title="Lawn",
            unique_id="zone-1",
        ),
    )
    manager = Mock()
    manager.snapshot.return_value = _snapshot(operation_enabled=False, automation_enabled=False)
    manager.async_set_installation_operation = AsyncMock(return_value={})
    manager.async_set_installation_automation = AsyncMock(return_value={})
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    for action in ("activate_installation", "enable_automatic"):
        result = await _open_installation_releases(hass, entry)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": action}
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfiguration_required"
    manager.async_set_installation_operation.assert_not_awaited()
    manager.async_set_installation_automation.assert_not_awaited()


async def test_action_results_and_status_are_german_when_ha_is_german(
    hass: HomeAssistant,
) -> None:
    """Localize backend-provided placeholders instead of exposing response keys."""
    hass.config.language = "de"
    entry = await _create_v2_entry(hass)
    manager = Mock()
    manager.snapshot.return_value = _snapshot(operation_enabled=False)
    manager.async_plan_automatic = AsyncMock(
        return_value={"created": 2, "replaced": 1, "removed": 3}
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["description_placeholders"] is None
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    assert result["description_placeholders"] == {
        "installation_status": "Deaktiviert",
        "automatic_status": "Aktiviert",
    }
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "replan"}
    )
    assert result["description_placeholders"]["result"] == (
        "Bewässerungsplanung neu berechnet: 2 erstellt, 1 ersetzt, 3 entfernt."
    )
