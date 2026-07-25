"""Version 2 config-flow behavior tests for Irrigation Manager."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN


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
            ({"meter_entity": "sensor.water"}, "installation_zone"),
            (
                {"name": "Lawn", "zone_valve": "switch.lawn", "control_type": "time"},
                "installation_schedule",
            ),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)
            assert result["step_id"] == expected_step
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "monday_start": "22:00:00",
                "monday_end": "00:30:00",
                "monday_target": 600,
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].version == 2
    assert result["data"] == {
        "name": "Garden",
        "operation_enabled": True,
        "automation_enabled": True,
        "main_valve": "switch.main",
        "meter_type": "cumulative",
        "meter_entity": "sensor.water",
    }
    zone = next(iter(result["result"].subentries.values()))
    assert len(zone.data["weekly_schedule"]) == 7
    assert zone.data["weekly_schedule"][0]["target"] == 600


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
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Beds",
            "zone_valve": "switch.beds",
            "control_type": "volume",
            "volume_max_runtime": 900,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monday_start": "04:00:00", "monday_target": 10}
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


async def test_zone_add_and_reconfigure_expose_only_v2_sections(hass: HomeAssistant) -> None:
    """Add and edit a zone without any guided, expert, profile, or safety path."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "minimal"
    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.return_value.hex = "zone-1"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "volume",
                "volume_max_runtime": 1200,
            },
        )
        assert result["step_id"] == "minimal_schedule"
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "friday_start": "05:00:00",
                "friday_end": "06:00:00",
                "friday_target": 25,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    zone = next(iter(entry.subentries.values()))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    assert result["menu_options"] == ["reconfigure_minimal", "releases", "calibration"]


async def test_installation_options_are_direct_v2_sections(hass: HomeAssistant) -> None:
    """Expose direct installation modules and runtime actions without v1 menus."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"] == [
        "basics",
        "main_valve",
        "meter",
        "installation_releases",
        "replan",
        "emergency_stop",
        "reset_safety",
        "physical_meter_correction",
    ]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "basics"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Back garden"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.title == "Back garden"
    assert "needs_reconfiguration" not in entry.data


async def test_only_complete_installation_reconfiguration_clears_migration_flag(
    hass: HomeAssistant,
) -> None:
    """Keep the aggregate migration lock through every individual settings section."""
    entry = await _create_v2_entry(hass)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, "needs_reconfiguration": True}
    )
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"][0] == "installation_reconfiguration"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "basics"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Still locked"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["needs_reconfiguration"] is True

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation_reconfiguration"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Reconfigured", "meter_type": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert "needs_reconfiguration" not in entry.data

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "installation_reconfiguration" not in result["menu_options"]
    assert "v2_installation" not in result["menu_options"]


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
        result["flow_id"], {"next_step_id": "meter"}
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
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    updated = entry.subentries[zone.subentry_id].data
    assert updated["expected_flow_l_min"] == 12.5
    assert updated["min_flow"] == 10.0
    assert updated["max_flow"] == 15.0
    assert updated["flow_calibrated_at"] == "2026-07-25T10:00:00+00:00"
    assert "volume_max_runtime" not in updated


async def test_installation_actions_and_physical_meter_correction_use_manager(
    hass: HomeAssistant,
) -> None:
    """Keep documented runtime actions available from installation settings."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    manager = Mock()
    manager.snapshot.return_value = SimpleNamespace(operation_enabled=True, automation_enabled=True)
    manager.automatic_execution_active.return_value = False
    manager.async_set_installation_operation = AsyncMock(return_value={"operation_enabled": True})
    manager.async_set_installation_automation = AsyncMock(
        return_value={"automation_enabled": False}
    )
    manager.async_correct_physical_meter = AsyncMock(
        return_value={"physical_total_liters": 1234.5, "correction_liters": 4.5}
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation_releases"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"operation_enabled": True, "automation_enabled": False}
    )
    assert result["step_id"] == "action_result"
    manager.async_set_installation_automation.assert_awaited_once_with(
        enabled=False, stop_active=False
    )

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
