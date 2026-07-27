"""Version 2 config-flow behavior tests for Irrigation Manager."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, section
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
                "monday": {"start": "22:00:00", "end": "00:30:00", "target": "00:10:00"},
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
            "volume_max_runtime": "00:15:00",
        },
    )
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
                "volume_max_runtime": "00:20:00",
            },
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
                "friday": {"start": "05:00:00", "end": "06:00:00", "target": 25},
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    zone = next(iter(entry.subentries.values()))
    assert zone.data["volume_max_runtime"] == 1_200
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    assert result["menu_options"] == ["reconfigure_minimal", "releases", "calibration"]


async def test_installation_configuration_is_atomic_multistep_wizard(
    hass: HomeAssistant,
) -> None:
    """Collect every installation setting before one final persisted update."""
    entry = await _create_v2_entry(hass, meter_type="cumulative")
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["menu_options"] == [
        "configuration",
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
        result["flow_id"], {"next_step_id": "configuration"}
    )
    assert result["step_id"] == "configuration"
    assert result["last_step"] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Back garden"}
    )
    assert result["step_id"] == "configuration_main_valve"
    assert result["last_step"] is False
    assert entry.title == "Garden"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"main_valve": "switch.main"}
    )
    assert result["step_id"] == "configuration_meter"
    assert result["last_step"] is False
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "pulse"}
    )
    assert result["step_id"] == "configuration_meter_details"
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
        result["flow_id"], {"next_step_id": "configuration"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Garden"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )
    assert result["last_step"] is False
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
            "volume_max_runtime": "01:00:00",
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"monday": {"start": "04:00:00", "end": "04:15:00", "target": 100}},
    )

    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[zone.subentry_id].data["weekly_schedule"][0]["target"] == 100.0


async def test_calibration_form_converts_hh_mm_ss_to_seconds(hass: HomeAssistant) -> None:
    """Keep calibration input readable while passing numeric seconds to the runtime."""
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
    assert duration_marker.default() == "00:01:00"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"duration": "00:02:03", "confirm_supervision": True}
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
        "configuration",
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
