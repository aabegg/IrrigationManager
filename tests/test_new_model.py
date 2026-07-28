"""Authoritative v2 configuration behavior."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager import async_migrate_entry
from custom_components.irrigation_manager.const import DOMAIN
from custom_components.irrigation_manager.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.irrigation_manager.executor import ExecutionResult
from custom_components.irrigation_manager.manager import _bounded_retry_delay
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
)
from custom_components.irrigation_manager.storage import IrrigationStore


async def _setup_v2_installation(
    hass: HomeAssistant,
    *,
    with_meter: bool = False,
    valve_open: bool = False,
    installation_overrides: dict[str, object] | None = None,
    zone_overrides: dict[str, object] | None = None,
) -> tuple[MockConfigEntry, ConfigSubentry]:
    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], "on")

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", "on" if valve_open else STATE_OFF)
    if with_meter:
        hass.states.async_set(
            "sensor.water",
            "100",
            {"unit_of_measurement": "L", "device_class": "water"},
        )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "none",
            **({"meter_type": "cumulative", "meter_entity": "sensor.water"} if with_meter else {}),
            "operation_enabled": True,
            "automation_enabled": True,
            **(installation_overrides or {}),
        },
        unique_id="installation-v2-runtime",
        version=2,
        minor_version=0,
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
                **(zone_overrides or {}),
                "weekly_schedule": [
                    {
                        "weekday": weekday,
                        "start": "04:00:00" if weekday == "monday" else None,
                        "end": "05:00:00" if weekday == "monday" else None,
                        "target": 600.0 if weekday == "monday" else None,
                    }
                    for weekday in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                ],
            }
        ),
        subentry_id="zone-v2-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-v2-runtime",
    )
    hass.config_entries.async_add_subentry(entry, zone)
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
    return entry, zone


async def test_stage1_migration_preserves_targets_as_day_overrides(
    hass: HomeAssistant,
) -> None:
    """Use the first old target as baseline without changing any old target."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "meter_type": "none"},
        unique_id="stage1-migration",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    schedule = [
        {
            "weekday": weekday,
            "start": "04:00:00" if weekday in {"monday", "friday"} else None,
            "end": "05:00:00" if weekday in {"monday", "friday"} else None,
            "target": 300.0 if weekday == "monday" else 600.0 if weekday == "friday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
            "weekly_schedule": schedule,
        },
        subentry_id="zone-stage1",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-stage1",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await async_migrate_entry(hass, entry)

    assert entry.minor_version == 3
    assert entry.data["plant_site_module_enabled"] is False
    migrated = entry.subentries[zone.subentry_id].data
    assert migrated["base_target"] == 300.0
    assert migrated["weekly_schedule"][0]["target"] == 300.0
    assert migrated["weekly_schedule"][4]["target"] == 600.0
    assert migrated["use_plant_site_model"] is False
    assert migrated["subareas"] == []


async def test_stage2_migration_adds_dormant_neutral_seasonal_configuration(
    hass: HomeAssistant,
) -> None:
    """Make existing zones season-ready without changing any planned target."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={
            "name": "Garden",
            "meter_type": "none",
            "seasonal_module_enabled": False,
        },
        unique_id="stage2-migration",
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data={
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
            "base_target": 600.0,
            "weekly_schedule": [],
        },
        subentry_id="zone-stage2",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-stage2",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await async_migrate_entry(hass, entry)

    migrated = entry.subentries[zone.subentry_id].data
    assert entry.minor_version == 3
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


async def test_stage1_migration_handles_empty_and_equal_target_schedules(
    hass: HomeAssistant,
) -> None:
    """Leave an empty baseline unset and preserve every equal legacy override."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "meter_type": "none"},
        unique_id="stage1-migration-edges",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    empty_zone = ConfigSubentry(
        data={
            "name": "Empty",
            "zone_valve": "switch.empty",
            "control_type": "time",
            "weekly_schedule": [],
        },
        subentry_id="empty-zone",
        subentry_type="zone",
        title="Empty",
        unique_id="empty-zone",
    )
    equal_zone = ConfigSubentry(
        data={
            "name": "Equal",
            "zone_valve": "switch.equal",
            "control_type": "time",
            "weekly_schedule": [
                {"weekday": "monday", "start": "04:00:00", "end": "05:00:00", "target": 300.0},
                {"weekday": "friday", "start": "04:00:00", "end": "05:00:00", "target": 300.0},
            ],
        },
        subentry_id="equal-zone",
        subentry_type="zone",
        title="Equal",
        unique_id="equal-zone",
    )
    hass.config_entries.async_add_subentry(entry, empty_zone)
    hass.config_entries.async_add_subentry(entry, equal_zone)

    assert await async_migrate_entry(hass, entry)

    migrated_empty = entry.subentries[empty_zone.subentry_id].data
    migrated_equal = entry.subentries[equal_zone.subentry_id].data
    assert "base_target" not in migrated_empty
    assert migrated_equal["base_target"] == 300.0
    assert [item["target"] for item in migrated_equal["weekly_schedule"]] == [300.0, 300.0]


async def test_common_baseline_resolves_without_day_override(hass: HomeAssistant) -> None:
    """Plan a window from the common baseline and record its provenance."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["base_target"] = 700.0
    manager._zone_configs[0].data["weekly_schedule"][0]["target"] = None
    manager._stored_state = replace(manager._stored_state, manual_requests=())

    report = await manager.async_plan_automatic(now=datetime(2026, 7, 26, 12, tzinfo=UTC))

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.target_value == 700.0
    assert request.resolved_inputs["base_target"] == 700.0
    assert request.resolved_inputs["day_target_override"] is None
    assert request.resolved_inputs["used_day_target_override"] is False


async def test_minimal_wizard_creates_installation_and_first_zone(
    hass: HomeAssistant,
    mock_setup_entry: None,
) -> None:
    """Create a usable time-controlled installation without optional modules."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    assert result["step_id"] == "create"

    with patch("custom_components.irrigation_manager.config_flow.uuid4") as uuid4:
        uuid4.side_effect = [
            type("Id", (), {"hex": "installation-v2"})(),
            type("Id", (), {"hex": "zone-v2"})(),
        ]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Garden"}
        )
        assert result["step_id"] == "installation_hardware"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        assert result["step_id"] == "installation_meter"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"meter_type": "none"}
        )
        assert result["step_id"] == "installation_extensions"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"plant_site_module_enabled": False}
        )
        assert result["step_id"] == "installation_zone"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Lawn", "zone_valve": "switch.lawn"}
        )
        assert result["step_id"] == "installation_baseline"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"base_target": {"hours": 0, "minutes": 30, "seconds": 0}},
        )
        assert result["step_id"] == "installation_schedule"
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
    entry = result["result"]
    assert entry.version == 2
    assert entry.data == {
        "name": "Garden",
        "main_valve": None,
        "meter_type": "none",
        "operation_enabled": True,
        "automation_enabled": True,
        "plant_site_module_enabled": False,
        "seasonal_module_enabled": False,
        "weather_module_enabled": False,
        "soak_module_enabled": False,
    }
    zone = next(iter(entry.subentries.values()))
    assert zone.unique_id == "zone-v2"
    assert zone.data["control_type"] == "time"
    assert zone.data["operation_enabled"] is True
    assert zone.data["automation_enabled"] is True
    assert zone.data["base_target"] == 1800
    assert len(zone.data["weekly_schedule"]) == 7
    assert zone.data["weekly_schedule"][0] == {
        "weekday": "monday",
        "start": "22:00:00",
        "end": "00:30:00",
        "target": None,
    }
    assert zone.data["weekly_schedule"][1] == {
        "weekday": "tuesday",
        "start": None,
        "end": None,
        "target": None,
    }


async def test_v2_creation_menu_has_no_zone_less_expert_path(hass: HomeAssistant) -> None:
    """Every ordinary v2 creation path must produce its first valid zone."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    assert result["menu_options"] == ["create"]


async def test_weekly_schedule_rejects_partial_and_overlapping_rows(
    hass: HomeAssistant,
) -> None:
    """Keep the seven-row schedule invalid until every configured row is complete and disjoint."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "create"}
    )
    for payload in (
        {"name": "Garden"},
        {},
        {"meter_type": "none"},
        {"plant_site_module_enabled": False},
        {"name": "Lawn", "zone_valve": "switch.lawn"},
        {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}},
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)

    partial = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"monday": {"start": "04:00:00", "target": {"hours": 0, "minutes": 10, "seconds": 0}}},
    )
    assert partial["step_id"] == "installation_schedule"
    assert partial["errors"] == {"base": "schedule_row_incomplete"}

    overlap = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "monday": {
                "start": "23:00:00",
                "end": "02:00:00",
                "target": {"hours": 0, "minutes": 30, "seconds": 0},
            },
            "tuesday": {
                "start": "01:00:00",
                "end": "03:00:00",
                "target": {"hours": 0, "minutes": 10, "seconds": 0},
            },
        },
    )
    assert overlap["step_id"] == "installation_schedule"
    assert overlap["errors"] == {"base": "schedule_overlap"}


async def test_v2_migration_disables_and_requires_reconfiguration(
    hass: HomeAssistant,
) -> None:
    """Do not invent weekly targets from legacy demand scheduling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Legacy garden",
        data={
            "name": "Legacy garden",
            "main_valve": "switch.main",
            "raw_meter": "sensor.pulses",
            "liters_per_count": 2.5,
            "automation_enabled": True,
            "weather_entity": "weather.home",
        },
        unique_id="legacy-installation",
        version=1,
        minor_version=8,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "automation_enabled": True,
                "watering_windows": ["04:00-06:00"],
                "plant_profile": "builtin:plant:cool-season-turf:v1",
                "default_duration": 600,
            }
        ),
        subentry_id="legacy-zone",
        subentry_type="zone",
        title="Lawn",
        unique_id="zone-lawn",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 2
    assert entry.minor_version == 3
    assert entry.data == {
        "name": "Legacy garden",
        "main_valve": "switch.main",
        "meter_type": "pulse",
        "meter_entity": "sensor.pulses",
        "liters_per_pulse": 2.5,
        "operation_enabled": False,
        "automation_enabled": False,
        "needs_reconfiguration": True,
        "plant_site_module_enabled": False,
        "seasonal_module_enabled": False,
        "weather_module_enabled": False,
        "soak_module_enabled": False,
    }
    assert dict(entry.subentries[zone.subentry_id].data) == {
        "name": "Lawn",
        "zone_valve": "switch.lawn",
        "control_type": "time",
        "operation_enabled": False,
        "automation_enabled": False,
        "weekly_schedule": [
            {"weekday": weekday, "start": None, "end": None, "target": None}
            for weekday in (
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            )
        ],
        "needs_reconfiguration": True,
        "use_plant_site_model": False,
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
        "subareas": [],
    }


async def test_v2_minor_migration_removes_only_retired_entity_unique_ids(
    hass: HomeAssistant,
) -> None:
    """Clean stale entity registrations without touching allowed renamed entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Garden",
        data={"name": "Garden", "meter_type": "none"},
        unique_id="migration-installation",
        version=2,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType({"name": "Lawn", "zone_valve": "switch.lawn"}),
        subentry_id="migration-zone-subentry",
        subentry_type="zone",
        title="Lawn",
        unique_id="migration-zone",
    )
    hass.config_entries.async_add_subentry(entry, zone)
    registry = er.async_get(hass)
    allowed = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "migration-zone_zone_status",
        config_entry=entry,
        suggested_object_id="legacy_zone_status",
    )
    registry.async_update_entity(allowed.entity_id, new_entity_id="sensor.renamed_zone_status")
    retired = {
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            "migration-installation_weather_model_quality",
            config_entry=entry,
        ).entity_id,
        registry.async_get_or_create(
            "binary_sensor",
            DOMAIN,
            "migration-zone_safety_lock",
            config_entry=entry,
        ).entity_id,
        registry.async_get_or_create(
            "calendar",
            DOMAIN,
            "migration-installation_calendar",
            config_entry=entry,
        ).entity_id,
    }

    assert await async_migrate_entry(hass, entry)

    assert entry.minor_version == 3
    assert registry.async_get("sensor.renamed_zone_status") is not None
    assert all(registry.async_get(entity_id) is None for entity_id in retired)


async def test_weekly_replan_atomically_replaces_only_pending_automatic_requests(
    hass: HomeAssistant,
) -> None:
    """Plan a bounded horizon while retaining manual and already active work."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    manual = ManualIrrigationRequest(
        request_id="manual-1",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=30,
        remaining_value=30,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=30)).isoformat(),
    )
    stale = replace(
        manual,
        request_id="automatic:stale",
        sequence=2,
        source="automatic",
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(manual, stale))

    report = await manager.async_plan_automatic(now=now)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert report["created"] == 2
    assert report["replaced"] == 0
    assert report["removed"] == 1
    assert next(request for request in stored.manual_requests if request.request_id == "manual-1")
    automatic = [request for request in stored.manual_requests if request.source == "automatic"]
    starts = [
        dt_util.as_local(datetime.fromisoformat(request.requested_start_at))
        for request in automatic
    ]
    assert [(start.date().isoformat(), start.hour) for start in starts] == [
        ("2026-07-27", 4),
        ("2026-08-03", 4),
    ]
    assert all(request.target_type == "duration" for request in automatic)
    assert all(request.target_value == 600 for request in automatic)


async def test_seasonal_plan_snapshots_interpolated_target_inputs(
    hass: HomeAssistant,
) -> None:
    """Resolve a scheduled baseline through the local seasonal curve once per order."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 1.0, "february": 2.0},
        },
    )
    manager = entry.runtime_data.manager

    report = await manager.async_plan_automatic(now=datetime(2026, 1, 4, 12, tzinfo=UTC))

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.target_value == pytest.approx(600.0 * (1.0 + 4 / 31))
    assert request.resolved_inputs["base_target"] == 600.0
    assert request.resolved_inputs["seasonal_factor"] == pytest.approx(1.0 + 4 / 31)
    assert request.resolved_inputs["seasonal_base_target"] == pytest.approx(600.0 * (1.0 + 4 / 31))
    assert request.resolved_inputs["target_resolution_outcome"] == "execute"
    assert request.resolved_inputs["fallback_strategy"] == "none"
    assert request.resolved_inputs["quality"] == "valid"
    assert request.resolved_inputs["warnings"] == []


async def test_invalid_seasonal_curve_fallback_is_snapshotted_and_logged_once(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep baseline irrigation safe while exposing corrupt curve evidence."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 0.0},
        },
    )
    manager = entry.runtime_data.manager
    now = datetime(2026, 1, 4, 12, tzinfo=UTC)
    caplog.clear()

    report = await manager.async_plan_automatic(now=now)

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.target_value == 600.0
    assert request.resolved_inputs["fallback_strategy"] == "base_target"
    assert request.resolved_inputs["quality"] == "fallback"
    assert request.resolved_inputs["warnings"] == ["invalid_seasonal_curve"]
    assert any("invalid_seasonal_curve" in record.getMessage() for record in caplog.records)
    caplog.clear()
    await manager.async_plan_automatic(now=now)
    assert not any("invalid_seasonal_curve" in record.getMessage() for record in caplog.records)


async def test_seasonal_curve_change_atomically_replaces_only_pending_automatic_work(
    hass: HomeAssistant,
) -> None:
    """Recalculate pending automatic orders while retaining manual work unchanged."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 1.0, "february": 1.0},
        },
    )
    manager = entry.runtime_data.manager
    now = datetime(2026, 1, 4, 12, tzinfo=UTC)
    first = await manager.async_plan_automatic(now=now)
    original = manager._request(first["created_request_ids"][0])
    assert original is not None
    manual = ManualIrrigationRequest(
        request_id="manual-seasonal-proof",
        sequence=99,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60.0,
        remaining_value=60.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(days=1)).isoformat(),
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(*manager._stored_state.manual_requests, manual),
    )
    manager._zone_configs[0].data["seasonal_factors"] = {
        "january": 1.5,
        "february": 1.5,
    }

    report = await manager.async_plan_automatic(now=now)

    replacement = manager._request(original.request_id)
    assert original.request_id in report["replaced_request_ids"]
    assert report["replaced"] == 2
    assert replacement is not None
    assert replacement.target_value == 900.0
    assert replacement.revision == original.revision + 1
    assert manager._request(manual.request_id) == manual


async def test_actual_seasonal_config_change_defers_reload_during_active_execution(
    hass: HomeAssistant,
) -> None:
    """Keep the immutable target snapshot of an already active automatic order."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 1.0, "february": 1.0},
        },
    )
    manager = entry.runtime_data.manager
    now = datetime(2026, 1, 4, 12, tzinfo=UTC)
    first = await manager.async_plan_automatic(now=now)
    original = manager._request(first["created_request_ids"][0])
    assert original is not None
    executing = replace(original, status="executing", execution_id="seasonal-active")
    active = ActiveExecutionState(
        zone_id=zone.unique_id,
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=None,
        prepared_at=now.isoformat(),
        watering_started_at=now.isoformat(),
        requested_duration_seconds=original.target_value,
        request_id=original.request_id,
        execution_id="seasonal-active",
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=tuple(
            executing if request.request_id == original.request_id else request
            for request in manager._stored_state.manual_requests
        ),
        active_execution=active,
    )
    changed_curve = {**zone.data["seasonal_factors"], "january": 1.5, "february": 1.5}
    hass.config_entries.async_update_subentry(
        entry,
        zone,
        data={**zone.data, "seasonal_factors": changed_curve},
    )
    for _ in range(5):
        await asyncio.sleep(0)
        if manager._config_reload_pending:
            break

    assert manager._config_reload_pending is True
    assert entry.subentries[zone.subentry_id].data["seasonal_factors"] == changed_curve
    assert manager._stored_state.active_execution == active
    assert manager._request(original.request_id) == executing
    assert (
        sum(
            request.request_id == original.request_id
            for request in manager._stored_state.manual_requests
        )
        == 1
    )
    assert manager._pending_reload_task is not None
    manager._pending_reload_task.cancel()
    await asyncio.gather(manager._pending_reload_task, return_exceptions=True)
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=tuple(
            replace(request, status="cancelled")
            if request.request_id == original.request_id
            else request
            for request in manager._stored_state.manual_requests
        ),
        active_execution=None,
    )
    manager._refresh_complete_idle_event()


async def test_seasonal_target_that_exceeds_window_is_reported_not_shortened(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Keep an enlarged seasonal target whole and expose why no order was created."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 3.0, "february": 3.0},
        },
    )
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["weekly_schedule"][0]["target"] = 1800.0

    report = await manager.async_plan_automatic(now=datetime(2026, 1, 4, 12, tzinfo=UTC))

    assert report["created"] == 0
    assert report["not_plannable"] == [
        {
            "request_id": "automatic:zone-v2-runtime:2026-01-05",
            "zone_id": "zone-v2-runtime",
            "reason": "seasonal_target_does_not_fit",
        },
        {
            "request_id": "automatic:zone-v2-runtime:2026-01-12",
            "zone_id": "zone-v2-runtime",
            "reason": "seasonal_target_does_not_fit",
        },
    ]
    assert manager.diagnostics_state_decisions()["planning_rejections"] == report["not_plannable"]
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert [rejection.as_dict() for rejection in stored.planning_rejections] == report[
        "not_plannable"
    ]
    manager._stored_state = replace(manager._stored_state, planning_rejections=())
    caplog.clear()
    rejections = list(stored.planning_rejections)
    assert manager._update_planning_observability(rejections, set()) is True
    assert manager._update_planning_observability(rejections, set()) is False
    assert (
        sum("seasonal_target_does_not_fit" in record.getMessage() for record in caplog.records) == 2
    )
    manager._zone_configs[0].data["seasonal_factors"] = {
        "january": 1.0,
        "february": 1.0,
    }
    await manager.async_plan_automatic(now=datetime(2026, 1, 4, 12, tzinfo=UTC))
    assert manager.diagnostics_state_decisions()["planning_rejections"] == []
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.planning_rejections == ()


async def test_failed_planning_rejection_persistence_is_retried(
    hass: HomeAssistant,
) -> None:
    """Keep unchanged rejection evidence dirty until a later store write succeeds."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={"seasonal_module_enabled": True},
        zone_overrides={
            "use_seasonal_adjustment": True,
            "seasonal_factors": {"january": 3.0, "february": 3.0},
        },
    )
    manager = entry.runtime_data.manager
    manager._stored_state = replace(manager._stored_state, manual_requests=())
    manager._zone_configs[0].data["weekly_schedule"][0]["target"] = 1800.0
    manager._store.async_save = AsyncMock(side_effect=[OSError("disk unavailable"), None])
    now = datetime(2026, 1, 4, 12, tzinfo=UTC)

    with pytest.raises(OSError, match="disk unavailable"):
        await manager.async_plan_automatic(now=now)

    assert manager._planning_rejections_dirty is True
    await manager.async_plan_automatic(now=now)
    assert manager._store.async_save.await_count == 2
    assert manager._planning_rejections_dirty is False


async def test_weekly_volume_plan_uses_calibrated_flow_without_weakening_hard_limit(
    hass: HomeAssistant,
) -> None:
    """Fit a volume order by calibrated duration while retaining its safety timeout."""
    entry, _zone = await _setup_v2_installation(
        hass,
        with_meter=True,
        zone_overrides={
            "control_type": "volume",
            "volume_max_runtime": 3600,
            "expected_flow_l_min": 10.0,
            "flow_calibrated_at": "2026-07-25T10:00:00+00:00",
        },
    )
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["weekly_schedule"] = [
        {
            "weekday": weekday,
            "start": "04:00:00" if weekday == "monday" else None,
            "end": "04:15:00" if weekday == "monday" else None,
            "target": 100.0 if weekday == "monday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]
    manager._stored_state = replace(manager._stored_state, manual_requests=())

    report = await manager.async_plan_automatic(now=datetime(2026, 7, 26, 12, tzinfo=UTC))

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.target_type == "volume"
    assert request.target_value == 100.0
    assert request.hard_time_limit_seconds == 3600
    assert request.delivery_runtime_limit_seconds == 3600
    assert request.resolved_inputs["planned_delivery_duration_seconds"] == 600.0
    assert request.resolved_inputs["planning_basis"] == "calibrated_flow"


async def test_weekly_volume_plan_without_flow_reserves_maximum_runtime(
    hass: HomeAssistant,
) -> None:
    """Keep conservative window planning until the zone has a flow profile."""
    entry, _zone = await _setup_v2_installation(
        hass,
        with_meter=True,
        zone_overrides={
            "control_type": "volume",
            "volume_max_runtime": 1800,
        },
    )
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["weekly_schedule"] = [
        {
            "weekday": weekday,
            "start": "04:00:00" if weekday == "monday" else None,
            "end": "05:00:00" if weekday == "monday" else None,
            "target": 100.0 if weekday == "monday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]
    manager._stored_state = replace(manager._stored_state, manual_requests=())

    report = await manager.async_plan_automatic(now=datetime(2026, 7, 26, 12, tzinfo=UTC))

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.resolved_inputs["planned_delivery_duration_seconds"] == 1800
    assert request.resolved_inputs["planning_basis"] == "maximum_runtime"


async def test_zone_edit_reloads_then_replans_pending_work_from_new_config(
    hass: HomeAssistant,
) -> None:
    """Never dispatch an old pending order after its valve and schedule were edited."""
    entry, zone = await _setup_v2_installation(hass)
    old_manager = entry.runtime_data.manager
    planning_now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    await old_manager.async_plan_automatic(now=planning_now)
    assert any(
        request.source == "automatic" and request.zone_valve == "switch.lawn"
        for request in old_manager._stored_state.manual_requests
    )
    hass.states.async_set("switch.new_lawn", STATE_OFF)

    with patch(
        "custom_components.irrigation_manager.manager.dt_util.now",
        return_value=planning_now,
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"),
            context={"source": "reconfigure", "subentry_id": zone.subentry_id},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "reconfigure_minimal"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {"name": "Lawn", "zone_valve": "switch.new_lawn", "control_type": "time"},
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
            result["flow_id"],
            {"base_target": {"hours": 0, "minutes": 5, "seconds": 0}},
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
            {
                "wednesday": {
                    "start": "06:00:00",
                    "end": "07:00:00",
                    "target": {"hours": 0, "minutes": 5, "seconds": 0},
                },
            },
        )
        assert result["type"] is FlowResultType.ABORT
        await hass.async_block_till_done()

    manager = entry.runtime_data.manager
    assert manager is not old_manager
    assert manager._zone_configs[0].data["zone_valve"] == "switch.new_lawn"
    automatic = [
        request
        for request in manager._stored_state.manual_requests
        if request.source == "automatic" and request.status == "pending"
    ]
    assert automatic
    assert {request.zone_valve for request in automatic} == {"switch.new_lawn"}
    assert {request.target_value for request in automatic} == {300.0}
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_weekly_replan_keeps_started_window_when_full_target_still_fits(
    hass: HomeAssistant,
) -> None:
    """Retain a current weekly opportunity and start it no earlier than replanning time."""
    entry, _ = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._stored_state = replace(manager._stored_state, manual_requests=())
    window_start = datetime.combine(
        date(2026, 7, 27), time(4), tzinfo=dt_util.DEFAULT_TIME_ZONE
    ).astimezone(UTC)
    initial = await manager.async_plan_automatic(now=window_start)
    before = manager._request(initial["created_request_ids"][0])
    assert before is not None

    now = window_start + timedelta(minutes=10)
    report = await manager.async_plan_automatic(now=now)

    after = manager._request(before.request_id)
    assert report["removed"] == 0
    assert report["replaced"] == 0
    assert after == before
    assert datetime.fromisoformat(after.requested_start_at or "") == window_start


async def test_weekly_replan_drops_started_window_when_full_target_no_longer_fits(
    hass: HomeAssistant,
) -> None:
    """Do not create a partial fixed weekly target after too much of its window elapsed."""
    entry, zone = await _setup_v2_installation(hass)
    hass.config_entries.async_update_subentry(
        entry,
        zone,
        data={
            **zone.data,
            "weekly_schedule": [
                {**row, "target": 3_001.0} if row["weekday"] == "monday" else row
                for row in zone.data["weekly_schedule"]
            ],
        },
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
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

    report = await manager.async_plan_automatic(
        dry_run=True,
        now=(
            datetime.combine(
                date(2026, 7, 27), time(4, 10), tzinfo=dt_util.DEFAULT_TIME_ZONE
            ).astimezone(UTC)
        ),
    )

    assert report["would_create_request_ids"] == []


async def test_unchanged_weekly_replan_preserves_request_and_sequence(
    hass: HomeAssistant,
) -> None:
    """Repeated planning must be a no-op for identical pending weekly opportunities."""
    entry, _ = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    await manager.async_plan_automatic(now=now)
    before = tuple(manager._stored_state.manual_requests)
    next_sequence = manager._stored_state.next_request_sequence

    report = await manager.async_plan_automatic(now=now)

    assert report["created"] == 0
    assert report["replaced"] == 0
    assert report["removed"] == 0
    assert manager._stored_state.manual_requests == before
    assert manager._stored_state.next_request_sequence == next_sequence


async def test_durable_releases_gate_manual_and_automatic_operation(
    hass: HomeAssistant,
) -> None:
    """Keep installation and zone operation/automation releases independent."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager

    await manager.async_set_installation_automation(enabled=False, stop_active=False)
    assert manager.snapshot().automation_enabled is False
    await manager.async_set_installation_operation(enabled=False)
    assert manager.snapshot().operation_enabled is False
    with pytest.raises(HomeAssistantError, match="operation"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )

    await manager.async_set_installation_operation(enabled=True)
    await manager.async_set_zone_operation(zone_subentry_id=zone.subentry_id, enabled=False)
    assert manager.snapshot().zone_operation_enabled[zone.unique_id] is False
    await manager.async_set_zone_automation(
        zone_subentry_id=zone.subentry_id, enabled=False, stop_active=False
    )
    assert manager.snapshot().zone_automation_enabled[zone.unique_id] is False


async def test_disabled_installation_does_not_supervise_external_valve_changes(
    hass: HomeAssistant,
) -> None:
    """Behave as if absent after deactivation instead of enforcing actuator state."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    await manager.async_set_installation_operation(enabled=False)

    hass.states.async_set("switch.lawn", "on")
    await hass.async_block_till_done()

    assert hass.states.get("switch.lawn").state == "on"
    assert manager.snapshot().installation_safety_lock is None


async def test_disabled_installation_does_not_enforce_valve_state_during_startup(
    hass: HomeAssistant,
) -> None:
    """Leave externally managed hardware untouched while starting disabled."""
    entry, _zone = await _setup_v2_installation(
        hass,
        valve_open=True,
        installation_overrides={"operation_enabled": False},
    )

    assert hass.states.get("switch.lawn").state == "on"
    assert entry.runtime_data.manager.snapshot().installation_safety_lock is None


@pytest.mark.parametrize("flag_scope", ["installation", "zone"])
async def test_reconfiguration_flags_block_activation_manual_dispatch_and_calibration(
    hass: HomeAssistant,
    flag_scope: str,
) -> None:
    """Keep every actuation boundary closed until the affected configuration is valid."""
    entry, zone = await _setup_v2_installation(
        hass,
        with_meter=True,
        installation_overrides={"needs_reconfiguration": flag_scope == "installation"},
        zone_overrides={"needs_reconfiguration": flag_scope == "zone"},
    )
    manager = entry.runtime_data.manager
    assert manager.snapshot().zone_status[zone.unique_id] == "needs_reconfiguration"

    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_set_installation_operation(enabled=True)
    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_set_installation_automation(enabled=True, stop_active=False)
    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_set_zone_operation(zone_subentry_id=zone.subentry_id, enabled=True)
    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_set_zone_automation(
            zone_subentry_id=zone.subentry_id, enabled=True, stop_active=False
        )

    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )
    with pytest.raises(HomeAssistantError, match="reconfiguration"):
        await manager.async_start_calibration(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
        )

    now = datetime.now(UTC)
    pending = ManualIrrigationRequest(
        request_id="flagged-pending",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        delivery_runtime_limit_seconds=1,
        operation_deadline_at=(now + timedelta(minutes=5)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(pending,))
    with patch.object(
        manager,
        "_async_expire_requests",
        wraps=manager._async_expire_requests,
    ) as expire_requests:
        manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
        manager._queue_event.set()
        await asyncio.sleep(0.01)

        assert expire_requests.await_count < 10

    assert hass.states.get("switch.lawn").state == STATE_OFF
    assert manager.list_manual_requests()[0]["status"] == "pending"
    manager._dispatcher_task.cancel()
    await asyncio.gather(manager._dispatcher_task, return_exceptions=True)
    manager._dispatcher_task = None


async def test_manual_targets_above_one_hour_use_submitted_runtime_and_reject_configured_max(
    hass: HomeAssistant,
) -> None:
    """Accept long duration and volume requests whole, never by silently capping them."""
    entry, zone = await _setup_v2_installation(
        hass,
        with_meter=True,
        zone_overrides={
            "max_delivery_runtime": 7200,
            "max_operation_lifetime": 7200,
            "volume_max_runtime": 7200,
        },
    )
    manager = entry.runtime_data.manager

    duration = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zone.subentry_id,
            "duration": 5400,
        },
        blocking=True,
        return_response=True,
    )
    volume = await hass.services.async_call(
        DOMAIN,
        "create_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zone.subentry_id,
            "amount": 100,
            "hard_time_limit": 5400,
        },
        blocking=True,
        return_response=True,
    )
    requests = {item.request_id: item for item in manager._stored_state.manual_requests}

    for request_id in (duration["request_id"], volume["request_id"]):
        request = requests[request_id]
        assert request.delivery_runtime_limit_seconds == 5400
        assert (
            datetime.fromisoformat(request.expires_at)
            - datetime.fromisoformat(request.requested_start_at or request.created_at)
        ).total_seconds() == 5400

    with pytest.raises(HomeAssistantError, match="7200"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=7201,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )
    with pytest.raises(HomeAssistantError, match="7200"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=None,
            amount_liters=100,
            hard_time_limit_seconds=7201,
            wait_for_completion=False,
        )


async def test_v2_config_edits_do_not_overwrite_disabled_durable_releases(
    hass: HomeAssistant,
) -> None:
    """Meter and schedule forms are configuration, not release controls."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    await manager.async_set_installation_automation(enabled=False, stop_active=False)
    await manager.async_set_zone_automation(
        zone_subentry_id=zone.subentry_id, enabled=False, stop_active=False
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_meter_only"}
    )
    assert "automation_enabled" not in {str(key) for key in result["data_schema"].schema}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert (await IrrigationStore(hass, entry.entry_id).async_load()).automation_enabled is False

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_minimal"}
    )
    assert "automation_enabled" not in {str(key) for key in result["data_schema"].schema}
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Lawn", "zone_valve": "switch.lawn", "control_type": "time"},
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
        {
            "monday": {
                "start": "06:00:00",
                "end": "07:00:00",
                "target": {"hours": 0, "minutes": 5, "seconds": 0},
            }
        },
    )
    assert result["type"] is FlowResultType.ABORT
    await hass.async_block_till_done()
    assert (await IrrigationStore(hass, entry.entry_id).async_load()).zone_automation_enabled[
        zone.unique_id
    ] is False
    await hass.config_entries.async_unload(entry.entry_id)


async def test_v2_zone_valves_cannot_collide_with_main_or_cross_entry_valves(
    hass: HomeAssistant,
) -> None:
    """Actuator ownership is global across installation and zone roles."""
    first = MockConfigEntry(
        domain=DOMAIN,
        title="First",
        data={"name": "First", "meter_type": "none", "main_valve": "switch.shared_main"},
        unique_id="first-v2",
        version=2,
    )
    first.add_to_hass(hass)
    hass.config_entries.async_add_subentry(
        first,
        ConfigSubentry(
            data=MappingProxyType({"name": "Lawn", "zone_valve": "switch.lawn"}),
            subentry_id="first-zone",
            subentry_type="zone",
            title="Lawn",
            unique_id="first-zone",
        ),
    )
    second = MockConfigEntry(
        domain=DOMAIN,
        title="Second",
        data={"name": "Second", "meter_type": "none"},
        unique_id="second-v2",
        version=2,
    )
    second.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (second.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Main collision", "zone_valve": "switch.shared_main"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "actuator_already_owned"

    result = await hass.config_entries.subentries.async_init(
        (second.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Zone collision", "zone_valve": "switch.lawn"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "actuator_already_owned"


async def test_timed_operation_without_meter_records_runtime_not_water(
    hass: HomeAssistant,
) -> None:
    """Do not turn an unmeasured duration into estimated consumption."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())

    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )

    execution = manager.list_irrigation_executions()[-1]
    assert execution["delivered_duration_seconds"] > 0
    assert execution["delivered_liters"] == 0
    assert execution["measurement_quality"] == "unavailable"


async def test_metered_timed_operation_completes_without_meter_progress_or_lock(
    hass: HomeAssistant,
) -> None:
    """A cumulative meter is observational for an ordinary time-controlled operation."""
    entry, zone = await _setup_v2_installation(hass, with_meter=True)
    manager = entry.runtime_data.manager
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())

    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )

    request = manager.list_manual_requests()[-1]
    assert request["status"] == "completed"
    assert manager.snapshot().installation_safety_lock is None


async def test_physical_meter_correction_is_audited_without_changing_consumption(
    hass: HomeAssistant,
) -> None:
    """Persist the physical reading adjustment separately from consumed water."""
    entry, _zone = await _setup_v2_installation(hass, with_meter=True)
    manager = entry.runtime_data.manager
    consumption_before = manager.snapshot().installation_total_liters

    result = await manager.async_correct_physical_meter(
        physical_total_liters=125.0,
        reason="Physical reading",
    )

    assert result["previous_total_liters"] == 100.0
    assert result["new_total_liters"] == 125.0
    assert result["difference_liters"] == 25.0
    assert result["reason"] == "Physical reading"
    assert manager.snapshot().installation_total_liters == consumption_before
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert stored.meter_correction_history[-1].as_dict() == result


async def test_release_and_unified_lock_actions_are_registered(
    hass: HomeAssistant,
) -> None:
    """Expose every new-model release and the canonical lock reset as native actions."""
    entry, zone = await _setup_v2_installation(hass)

    response = await hass.services.async_call(
        DOMAIN,
        "set_installation_operation",
        {"config_entry_id": entry.entry_id, "enabled": False},
        blocking=True,
        return_response=True,
    )
    assert response == {"operation_enabled": False}
    response = await hass.services.async_call(
        DOMAIN,
        "set_zone_automation",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": zone.subentry_id,
            "enabled": False,
            "stop_active": False,
        },
        blocking=True,
        return_response=True,
    )
    assert response["automation_enabled"] is False

    await entry.runtime_data.manager.async_emergency_stop()
    assert entry.runtime_data.manager.snapshot().installation_safety_lock is not None
    await hass.services.async_call(
        DOMAIN,
        "reset_safety_lock",
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )
    assert entry.runtime_data.manager.snapshot().installation_safety_lock is None


async def test_no_meter_exposes_runtime_contract_without_water_entities(
    hass: HomeAssistant,
) -> None:
    """Reserve water and Energy Dashboard entities for configured measurements."""
    entry, zone = await _setup_v2_installation(hass)
    registry = er.async_get(hass)

    assert entry.minor_version == 3
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, "installation-v2-runtime_water_total")
        is None
    )
    assert registry.async_get_entity_id("sensor", DOMAIN, "zone-v2-runtime_water_total") is None
    snapshot = entry.runtime_data.manager.snapshot()
    assert snapshot.runtime_today_seconds == 0
    assert snapshot.runtime_month_seconds == 0
    assert snapshot.zone_runtime_today_seconds[zone.unique_id] == 0


@pytest.mark.parametrize(
    ("ended_at", "duration", "now", "expected_today", "expected_month"),
    [
        (
            "2026-07-24T00:10:00+02:00",
            1_200.0,
            datetime(2026, 7, 24, 12, tzinfo=ZoneInfo("Europe/Berlin")),
            600.0,
            1_200.0,
        ),
        (
            "2026-08-01T00:20:00+02:00",
            1_800.0,
            datetime(2026, 8, 1, 12, tzinfo=ZoneInfo("Europe/Berlin")),
            1_200.0,
            1_200.0,
        ),
    ],
)
async def test_runtime_periods_split_at_local_midnight_and_month_end(
    hass: HomeAssistant,
    ended_at: str,
    duration: float,
    now: datetime,
    expected_today: float,
    expected_month: float,
) -> None:
    """Allocate elapsed delivery time to the local periods it actually occupied."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    execution = IrrigationExecutionState(
        execution_id="execution-period",
        request_id="request-period",
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=duration,
        remaining_value=0,
        status="completed",
        created_at=(datetime.fromisoformat(ended_at) - timedelta(seconds=duration)).isoformat(),
        delivered_duration_seconds=duration,
        ended_at=ended_at,
    )
    manager._stored_state = replace(manager._stored_state, irrigation_executions=(execution,))
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Berlin")),
        patch("custom_components.irrigation_manager.manager.dt_util.now", return_value=now),
    ):
        manager._publish(status="idle", active_zone_id=None)

    snapshot = manager.snapshot()
    assert snapshot.runtime_today_seconds == expected_today
    assert snapshot.runtime_month_seconds == expected_month
    assert snapshot.zone_runtime_today_seconds[zone.unique_id] == expected_today
    assert snapshot.zone_runtime_month_seconds[zone.unique_id] == expected_month


@pytest.mark.parametrize(
    ("now", "start", "end", "expected_start", "expected_end"),
    [
        (
            datetime(2026, 3, 28, 12, tzinfo=UTC),
            "02:30:00",
            "04:00:00",
            "2026-03-29T01:30:00+00:00",
            "2026-03-29T02:00:00+00:00",
        ),
        (
            datetime(2026, 10, 24, 12, tzinfo=UTC),
            "02:30:00",
            "03:30:00",
            "2026-10-25T00:30:00+00:00",
            "2026-10-25T02:30:00+00:00",
        ),
    ],
)
async def test_weekly_planning_has_deterministic_dst_gap_and_fold_policy(
    hass: HomeAssistant,
    now: datetime,
    start: str,
    end: str,
    expected_start: str,
    expected_end: str,
) -> None:
    """Normalize gaps forward and choose the first occurrence of folded wall times."""
    entry, zone = await _setup_v2_installation(hass)
    sunday_schedule = [
        {
            "weekday": weekday,
            "start": start if weekday == "sunday" else None,
            "end": end if weekday == "sunday" else None,
            "target": 600.0 if weekday == "sunday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]
    hass.config_entries.async_update_subentry(
        entry, zone, data={**zone.data, "weekly_schedule": sunday_schedule}
    )
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["weekly_schedule"] = sunday_schedule
    manager._stored_state = replace(manager._stored_state, manual_requests=())
    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Berlin")):
        report = await manager.async_plan_automatic(now=now)

    request = manager._request(report["created_request_ids"][0])
    assert request is not None
    assert request.requested_start_at == expected_start
    assert request.automatic_window_end == expected_end


async def test_v2_subentry_flow_adds_another_minimal_zone(hass: HomeAssistant) -> None:
    """Keep repeatable zone setup on the same minimal canonical model."""
    entry, _ = await _setup_v2_installation(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"), context={"source": SOURCE_USER}
    )
    assert result["step_id"] == "minimal"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"name": "Beds", "zone_valve": "switch.beds", "control_type": "time"},
    )
    assert result["step_id"] == "baseline"
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}},
    )
    assert result["step_id"] == "minimal_schedule"
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    added = next(subentry for subentry in entry.subentries.values() if subentry.title == "Beds")
    assert len(added.data["weekly_schedule"]) == 7
    assert added.data["operation_enabled"] is True
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_options_block_meter_removal_while_volume_zone_exists(
    hass: HomeAssistant,
) -> None:
    """Require explicit conversion of every volume-controlled zone before meter removal."""
    entry, zone = await _setup_v2_installation(hass)
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            "meter_type": "cumulative",
            "meter_entity": "sensor.water",
        },
    )
    hass.config_entries.async_update_subentry(
        entry,
        zone,
        data={**zone.data, "control_type": "volume", "volume_max_runtime": 3600},
    )

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "configuration_meter_only"}
    )
    assert result["step_id"] == "configuration_meter_only"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"meter_type": "none"}
    )

    assert result["step_id"] == "configuration_meter_only"
    assert result["errors"] == {"base": "meter_required_by_volume_zones"}
    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_v2_reconfiguration_clears_flag_only_after_validation(
    hass: HomeAssistant,
) -> None:
    """Make destructively migrated installations operable from their settings forms."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Migrated garden",
        data={
            "name": "Migrated garden",
            "meter_type": "none",
            "operation_enabled": False,
            "automation_enabled": False,
            "needs_reconfiguration": True,
        },
        unique_id="migrated-v2",
        version=2,
    )
    entry.add_to_hass(hass)
    zone = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Lawn",
                "zone_valve": "switch.lawn",
                "control_type": "time",
                "operation_enabled": False,
                "automation_enabled": False,
                "weekly_schedule": [
                    {"weekday": weekday, "start": None, "end": None, "target": None}
                    for weekday in (
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    )
                ],
                "needs_reconfiguration": True,
            }
        ),
        subentry_id="migrated-zone",
        subentry_type="zone",
        title="Lawn",
        unique_id="migrated-lawn",
    )
    hass.config_entries.async_add_subentry(entry, zone)

    options = await hass.config_entries.options.async_init(entry.entry_id)
    assert options["menu_options"] == [
        "configuration",
        "extensions",
        "releases",
        "replan",
    ]
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"next_step_id": "configuration"}
    )
    installation_fields = {str(key) for key in options["data_schema"].schema}
    assert {"operation_enabled", "automation_enabled"}.isdisjoint(installation_fields)
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {"name": "Migrated garden"},
    )
    options = await hass.config_entries.options.async_configure(options["flow_id"], {})
    assert entry.data["needs_reconfiguration"] is True
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"meter_type": "none"}
    )
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert "needs_reconfiguration" not in entry.data

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "zone"),
        context={"source": "reconfigure", "subentry_id": zone.subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"next_step_id": "reconfigure_minimal"}
    )
    zone_fields = {str(key) for key in result["data_schema"].schema}
    assert {"operation_enabled", "automation_enabled"}.isdisjoint(zone_fields)
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "Lawn",
            "zone_valve": "switch.lawn",
            "control_type": "time",
        },
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"base_target": {"hours": 0, "minutes": 10, "seconds": 0}},
    )
    invalid = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"monday": {"start": "04:00:00", "target": {"hours": 0, "minutes": 10, "seconds": 0}}},
    )
    assert invalid["errors"] == {"base": "schedule_row_incomplete"}
    assert entry.subentries[zone.subentry_id].data["needs_reconfiguration"] is True
    completed = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "monday": {
                "start": "04:00:00",
                "end": "05:00:00",
                "target": {"hours": 0, "minutes": 10, "seconds": 0},
            },
        },
    )
    assert completed["type"] is FlowResultType.ABORT
    assert "needs_reconfiguration" not in entry.subentries[zone.subentry_id].data


async def test_v2_settings_separate_release_controls_reset_and_replan(
    hass: HomeAssistant,
) -> None:
    """Expose release controls separately while retaining reset and replanning."""
    entry, _ = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "deactivate_installation"}
    )
    assert result["description_placeholders"]["result"] == (
        "The irrigation installation was deactivated and active irrigation was stopped."
    )
    assert manager.snapshot().operation_enabled is False

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "releases"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "disable_automatic"}
    )
    assert result["description_placeholders"]["result"] == ("Automatic irrigation was disabled.")
    assert manager.snapshot().automation_enabled is False

    await manager.async_set_installation_operation(enabled=True)
    await manager.async_emergency_stop()
    assert manager.snapshot().emergency_stop is True

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert "emergency_stop" not in result["menu_options"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset_safety"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_reset": False}
    )
    assert result["errors"] == {"base": "reset_confirmation_required"}
    assert manager.snapshot().emergency_stop is True
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"confirm_reset": True}
    )
    assert manager.snapshot().emergency_stop is False
    assert result["step_id"] == "action_result"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "replan"}
    )
    assert result["description_placeholders"]["result"].startswith("Replanning completed:")


@pytest.mark.parametrize(
    ("scope", "choice", "expected_stop"),
    [
        ("installation", "stop", True),
        ("installation", "finish", False),
        ("zone", "stop", True),
        ("zone", "finish", False),
    ],
)
async def test_automation_disable_actions_ask_how_to_handle_active_execution(
    hass: HomeAssistant,
    scope: str,
    choice: str,
    expected_stop: bool,
) -> None:
    """Pass the explicit stop-or-finish choice for each durable automation scope."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    target_method = (
        "async_set_installation_automation"
        if scope == "installation"
        else "async_set_zone_automation"
    )
    with (
        patch.object(manager, "automatic_execution_active", return_value=True),
        patch.object(manager, target_method, new_callable=AsyncMock, return_value={}) as update,
    ):
        if scope == "installation":
            result = await hass.config_entries.options.async_init(entry.entry_id)
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "releases"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "disable_automatic"}
            )
            configure = hass.config_entries.options.async_configure
            expected_step = "disable_automatic"
        else:
            result = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "zone"),
                context={"source": "reconfigure", "subentry_id": zone.subentry_id},
            )
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], {"next_step_id": "releases"}
            )
            configure = hass.config_entries.subentries.async_configure
            result = await configure(result["flow_id"], {"next_step_id": "disable_zone_automatic"})
            expected_step = "disable_zone_automatic"
        assert result["step_id"] == expected_step
        result = await configure(result["flow_id"], {"active_execution": choice})

    if scope == "installation":
        assert result["step_id"] == "action_result"
        update.assert_awaited_once_with(enabled=False, stop_active=expected_stop)
    else:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == (
            "zone_automatic_disabled_stopped" if expected_stop else "zone_automatic_disabled"
        )
        update.assert_awaited_once_with(
            zone_subentry_id=zone.subentry_id,
            enabled=False,
            stop_active=expected_stop,
        )


@pytest.mark.parametrize("scope", ["installation", "zone"])
async def test_automation_disable_does_not_ask_without_relevant_active_execution(
    hass: HomeAssistant, scope: str
) -> None:
    """Apply an idle automation disable directly without an unnecessary choice."""
    entry, zone = await _setup_v2_installation(hass)
    if scope == "installation":
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "releases"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "disable_automatic"}
        )
        assert result["step_id"] == "action_result"
    else:
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, "zone"),
            context={"source": "reconfigure", "subentry_id": zone.subentry_id},
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "releases"}
        )
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {"next_step_id": "disable_zone_automatic"}
        )
        assert result["type"] is FlowResultType.ABORT

    assert result.get("step_id") not in {
        "disable_automatic",
        "disable_zone_automatic",
    }


async def test_cancelled_execution_is_accounted_exactly_once(hass: HomeAssistant) -> None:
    """Leave terminal ownership with the dispatcher when cancellation wakes the executor."""
    entry, zone = await _setup_v2_installation(hass, with_meter=True)
    manager = entry.runtime_data.manager
    started = asyncio.Event()

    async def execute(_request) -> ExecutionResult:
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return ExecutionResult(
                zone_id=zone.unique_id,
                delivered_liters=5,
                duration_seconds=1,
                stopped=True,
            )

    manager._executor.execute = execute
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    response = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=60,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await started.wait()

    await manager.async_cancel_request(str(response["request_id"]))

    assert manager._stored_state.installation_total_liters == 5
    assert manager._stored_state.zone_totals_liters[zone.unique_id] == 5
    execution = manager._stored_state.irrigation_executions[-1]
    assert execution.delivered_liters == 5
    assert execution.status == "cancelled"


async def test_stale_execution_id_cannot_stop_replacement_execution(
    hass: HomeAssistant,
) -> None:
    """Keep a stale card action scoped to the execution it originally displayed."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )
    stale_execution_id = str(manager.list_irrigation_executions()[-1]["execution_id"])
    replacement_started = asyncio.Event()

    async def execute(_request) -> ExecutionResult:
        replacement_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            return ExecutionResult(
                zone_id=zone.unique_id,
                delivered_liters=0,
                duration_seconds=0,
                stopped=True,
            )

    manager._executor.execute = execute
    replacement = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=60,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )
    await replacement_started.wait()
    replacement_execution_id = manager.snapshot().active_execution_id

    with pytest.raises(HomeAssistantError, match="already final"):
        await manager.async_stop(execution_id=stale_execution_id)

    assert manager.snapshot().active_execution_id == replacement_execution_id
    await manager.async_cancel_request(str(replacement["request_id"]))


@pytest.mark.parametrize("stop_kind", ["deactivate", "stop", "emergency"])
async def test_calibration_stop_owner_prevents_late_proposal_rewrite(
    hass: HomeAssistant, stop_kind: str
) -> None:
    """Cancel and await calibration before a stop action publishes terminal state."""
    entry, zone = await _setup_v2_installation(hass, with_meter=True)
    manager = entry.runtime_data.manager
    started = asyncio.Event()

    async def execute(_request) -> ExecutionResult:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    manager._executor.execute = execute
    response = await manager.async_start_calibration(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=60,
    )
    await started.wait()
    proposal_before = manager._stored_state.calibration_proposal

    if stop_kind == "deactivate":
        await manager.async_set_installation_operation(enabled=False)
    elif stop_kind == "stop":
        await manager.async_stop(execution_id=str(response["test_id"]))
    else:
        await manager.async_emergency_stop()

    assert manager._calibration_task is None
    assert manager._stored_state.active_execution is None
    assert manager._stored_state.calibration_proposal is proposal_before
    request = manager._request(f"calibration:{response['test_id']}")
    assert request is not None
    assert request.status == "cancelled"


async def test_dispatch_wake_timeout_includes_future_requested_start(
    hass: HomeAssistant,
) -> None:
    """Wake for readiness rather than sleeping until the request expires."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="future",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=now.isoformat(),
        requested_start_at=(now + timedelta(seconds=10)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))

    timeout = manager._seconds_until_next_request_change()

    assert timeout is not None
    assert 0 < timeout <= 10


async def test_dispatch_wake_timeout_ignores_past_requested_start(
    hass: HomeAssistant,
) -> None:
    """Do not spin on a due request that remains pending until its future deadline."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="due-but-blocked",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        requested_start_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))

    timeout = manager._seconds_until_next_request_change()

    assert timeout is not None
    assert 299 < timeout <= 300


async def test_due_blocked_request_is_diagnosed_once_without_busy_loop(
    hass: HomeAssistant,
) -> None:
    """Persist one stable transition for a blocked due request and then wait."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={"operation_enabled": False},
    )
    manager = entry.runtime_data.manager
    manager._dispatcher_task = entry.async_create_background_task(
        hass,
        manager._async_dispatch_requests(),
        "test request dispatcher",
    )
    await asyncio.sleep(0.05)
    assert manager._dispatcher_task is not None
    assert not manager._dispatcher_task.done()
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="blocked-diagnostic",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        requested_start_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
    )
    async with manager._command_lock:
        manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
        manager._queue_event.set()
    await asyncio.sleep(0.05)
    first = await async_get_config_entry_diagnostics(hass, entry)
    manager._queue_event.set()
    await asyncio.sleep(0.05)
    second = await async_get_config_entry_diagnostics(hass, entry)

    dispatcher = second["dispatcher"]
    assert dispatcher["current_reason"] == "operation_disabled"
    assert dispatcher["current_request_id"] == "blocked-diagnostic"
    assert dispatcher["blocked_since"] is not None
    transitions = [
        event
        for event in second["dispatcher_history"]
        if event["new_reason"] == "operation_disabled"
    ]
    assert len(transitions) == 1
    assert second["dispatcher_history"] == first["dispatcher_history"]


async def test_dispatcher_retries_unexpected_failure_with_backoff(
    hass: HomeAssistant,
) -> None:
    """An internal exception must not turn the background dispatcher into a hot loop."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._dispatcher_task = entry.async_create_background_task(
        hass,
        manager._async_dispatch_requests(),
        "test request dispatcher",
    )
    await asyncio.sleep(0.05)
    assert manager._dispatcher_task is not None
    assert not manager._dispatcher_task.done()
    calls = 0

    async def fail_expiry() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic dispatcher failure")

    async with manager._command_lock:
        manager._async_expire_requests = fail_expiry
        manager._queue_event.set()
    await asyncio.sleep(0.1)

    assert calls == 1
    diagnostics = manager.diagnostics_state_decisions()
    assert diagnostics["dispatcher"]["current_reason"] == "dispatcher_error"
    assert diagnostics["dispatcher"]["last_error"] == "RuntimeError"


async def test_dispatcher_cleanup_failure_is_logged_without_killing_task(
    hass: HomeAssistant,
) -> None:
    """Keep the dispatcher supervised when its final presentation refresh fails."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._dispatcher_task = entry.async_create_background_task(
        hass,
        manager._async_dispatch_requests(),
        "test request dispatcher",
    )
    await asyncio.sleep(0.05)

    def fail_publish(*, status: str, active_zone_id: str | None) -> None:
        del status, active_zone_id
        raise RuntimeError("synthetic publish failure")

    async with manager._command_lock:
        manager._publish = fail_publish
        manager._queue_event.set()
    await asyncio.sleep(0.1)

    assert manager._dispatcher_task is not None
    assert not manager._dispatcher_task.done()
    diagnostics = manager.diagnostics_state_decisions()
    assert diagnostics["dispatcher"]["current_reason"] == "dispatcher_error"
    assert diagnostics["dispatcher"]["last_error"] == "RuntimeError"


async def test_automatic_planner_failure_is_logged_and_retried_with_backoff(
    hass: HomeAssistant,
) -> None:
    """Retain evidence when automatic planning fails instead of sleeping silently."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    calls = 0

    async def fail_planning(*, dry_run: bool = False, now=None) -> dict[str, object]:
        del dry_run, now
        nonlocal calls
        calls += 1
        raise RuntimeError("synthetic planning failure")

    manager.async_plan_automatic = fail_planning
    manager._automatic_planner_task = entry.async_create_background_task(
        hass,
        manager._async_automatic_planner(),
        "test automatic planner",
    )
    await asyncio.sleep(0.1)

    assert calls == 1
    assert manager._automatic_planner_task is not None
    assert not manager._automatic_planner_task.done()
    diagnostic = manager.diagnostics_state_decisions()["dispatcher"]
    assert diagnostic["current_reason"] == "automatic_planning_error"
    assert diagnostic["last_error"] == "RuntimeError"


async def test_failed_diagnostic_write_is_retried_without_duplicate_transition(
    hass: HomeAssistant,
) -> None:
    """Retry a lost telemetry write even when the dispatcher decision is unchanged."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="retry-diagnostic",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    decision = manager._dispatch_decision(request, now=now)
    original_history_size = len(manager._stored_state.dispatcher_diagnostic_history)
    manager._store.async_save = AsyncMock(side_effect=[RuntimeError("storage unavailable"), None])

    await manager._async_record_dispatch_decision(decision)
    assert manager._diagnostics_dirty is True
    history_size_after_failure = len(manager._stored_state.dispatcher_diagnostic_history)
    await manager._async_record_dispatch_decision(decision)

    assert manager._store.async_save.await_count == 2
    assert manager._diagnostics_dirty is False
    assert history_size_after_failure == original_history_size + 1
    assert len(manager._stored_state.dispatcher_diagnostic_history) == history_size_after_failure


async def test_same_block_reason_metadata_update_preserves_original_block_start(
    hass: HomeAssistant,
) -> None:
    """Update wake metadata without inventing another decision transition."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={"operation_enabled": False},
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="stable-block",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1,
        remaining_value=1,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    decision = manager._dispatch_decision(request, now=now)
    await manager._async_record_dispatch_decision(decision)
    first = manager._stored_state.dispatcher_diagnostic
    history_size = len(manager._stored_state.dispatcher_diagnostic_history)
    assert first is not None

    await manager._async_record_dispatch_decision(
        replace(decision, next_wake_at=(now + timedelta(minutes=30)).isoformat())
    )
    updated = manager._stored_state.dispatcher_diagnostic

    assert updated is not None
    assert updated.blocked_since == first.blocked_since
    assert len(manager._stored_state.dispatcher_diagnostic_history) == history_size


def test_dispatch_retry_delay_is_bounded_without_large_integer_conversion() -> None:
    """Remain at the 60-second ceiling for arbitrarily many failures."""
    assert [_bounded_retry_delay(index) for index in range(1, 9)] == [
        1,
        2,
        4,
        8,
        16,
        32,
        60,
        60,
    ]
    assert _bounded_retry_delay(1_000_000) == 60


async def test_completion_and_pending_cancellation_close_diagnostic_request(
    hass: HomeAssistant,
) -> None:
    """Record terminal evidence before the dispatcher advances to later work."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    pending = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=1,
        amount_liters=None,
        hard_time_limit_seconds=None,
        requested_start_at=datetime.now(UTC) + timedelta(hours=1),
        wait_for_completion=False,
    )
    pending_second = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=1,
        amount_liters=None,
        hard_time_limit_seconds=None,
        requested_start_at=datetime.now(UTC) + timedelta(hours=2),
        wait_for_completion=False,
    )
    await manager.async_cancel_request(str(pending["request_id"]))
    await manager.async_cancel_request(str(pending_second["request_id"]))

    manager._dispatcher_task = entry.async_create_background_task(
        hass,
        manager._async_dispatch_requests(),
        "test request dispatcher",
    )
    completed = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=0.001,
        amount_liters=None,
        hard_time_limit_seconds=None,
    )
    terminal_reasons = {
        (event.request_id, event.new_reason)
        for event in manager._stored_state.dispatcher_diagnostic_history
    }

    assert (str(pending["request_id"]), "cancelled") in terminal_reasons
    assert (str(pending_second["request_id"]), "cancelled") in terminal_reasons
    assert (str(completed["request_id"]), "completed") in terminal_reasons


async def test_bulk_automatic_cancellation_records_every_affected_request(
    hass: HomeAssistant,
) -> None:
    """Do not collapse several automatic cancellations into one terminal event."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    requests = tuple(
        ManualIrrigationRequest(
            request_id=f"automatic-cancel-{index}",
            sequence=index,
            zone_id=zone.unique_id,
            zone_subentry_id=zone.subentry_id,
            zone_name=zone.title,
            zone_valve="switch.lawn",
            main_valve=None,
            target_type="duration",
            target_value=60,
            remaining_value=60,
            created_at=now.isoformat(),
            requested_start_at=(now + timedelta(hours=index)).isoformat(),
            expires_at=(now + timedelta(hours=index + 1)).isoformat(),
            source="automatic",
            automatic_window_end=(now + timedelta(hours=index + 1)).isoformat(),
        )
        for index in (1, 2)
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=requests)

    await manager.async_set_installation_automation(enabled=False, stop_active=False)

    cancelled_ids = {
        event.request_id
        for event in manager._stored_state.dispatcher_diagnostic_history
        if event.new_reason == "cancelled"
    }
    assert cancelled_ids >= {"automatic-cancel-1", "automatic-cancel-2"}


async def test_dispatch_decision_uses_stable_reason_codes_for_every_release_path(
    hass: HomeAssistant,
) -> None:
    """Keep the diagnostic vocabulary deterministic across all dispatcher barriers."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    manual = ManualIrrigationRequest(
        request_id="reason-matrix",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )

    assert manager._dispatch_decision(None, now=now).reason == "waiting_for_start"
    assert manager._dispatch_decision(manual, now=now).reason == "ready"

    manager._config_reload_pending = True
    assert manager._dispatch_decision(manual, now=now).reason == "config_reload_pending"
    manager._config_reload_pending = False
    manager._automatic_planning_in_progress = True
    assert manager._dispatch_decision(manual, now=now).reason == "automatic_planning_in_progress"
    manager._automatic_planning_in_progress = False

    manager._installation_data["needs_reconfiguration"] = True
    assert manager._dispatch_decision(manual, now=now).reason == "reconfiguration_required"
    manager._installation_data["needs_reconfiguration"] = False
    manager._stored_state = replace(manager._stored_state, operation_enabled=False)
    assert manager._dispatch_decision(manual, now=now).reason == "operation_disabled"
    manager._stored_state = replace(
        manager._stored_state,
        operation_enabled=True,
        emergency_stop=True,
        installation_safety_lock="Emergency stop activated",
    )
    assert manager._dispatch_decision(manual, now=now).reason == "emergency_stop"
    manager._stored_state = replace(
        manager._stored_state,
        emergency_stop=False,
        installation_safety_lock="Flow failure",
    )
    safety_decision = manager._dispatch_decision(manual, now=now)
    assert safety_decision.reason == "safety_lock"
    assert safety_decision.locks == {"safety_lock": "Flow failure"}
    manager._stored_state = replace(manager._stored_state, installation_safety_lock=None)

    mismatch = replace(manual, zone_valve="switch.replaced")
    assert manager._dispatch_decision(mismatch, now=now).reason == "actuator_snapshot_mismatch"
    manager._stored_state = replace(
        manager._stored_state,
        zone_operation_enabled={str(zone.unique_id): False},
    )
    assert manager._dispatch_decision(manual, now=now).reason == "zone_disabled"
    manager._stored_state = replace(
        manager._stored_state,
        zone_operation_enabled={str(zone.unique_id): True},
    )

    automatic = replace(
        manual,
        source="automatic",
        automatic_window_end=(now + timedelta(hours=1)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, automation_enabled=False)
    assert manager._dispatch_decision(automatic, now=now).reason == "automation_disabled"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        zone_automation_enabled={str(zone.unique_id): False},
    )
    assert manager._dispatch_decision(automatic, now=now).reason == "zone_automation_disabled"
    manager._stored_state = replace(
        manager._stored_state,
        zone_automation_enabled={str(zone.unique_id): True},
    )
    too_late = replace(
        automatic,
        automatic_window_end=(now + timedelta(seconds=10)).isoformat(),
    )
    assert manager._dispatch_decision(too_late, now=now).reason == "window_no_longer_fits"


async def test_clean_shutdown_and_unclean_restart_are_durable(
    hass: HomeAssistant,
) -> None:
    """Distinguish orderly unload from a previous runtime that never closed."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    diagnostic = manager._stored_state.dispatcher_diagnostic
    assert diagnostic is not None
    manager._stored_state = replace(
        manager._stored_state,
        dispatcher_diagnostic=replace(
            diagnostic,
            current_reason="safety_lock",
            clean_shutdown=False,
        ),
    )
    await manager._store.async_save(manager._stored_state)

    await manager._async_begin_boot_diagnostics()
    after_restart = await IrrigationStore(hass, entry.entry_id).async_load()
    restarted = after_restart.dispatcher_diagnostic
    assert restarted is not None
    assert restarted.current_reason == "unclean_restart"
    assert restarted.clean_shutdown is False
    assert after_restart.dispatcher_diagnostic_history[-1].old_reason == "safety_lock"

    await manager.async_shutdown()
    after_shutdown = await IrrigationStore(hass, entry.entry_id).async_load()
    stopped = after_shutdown.dispatcher_diagnostic
    assert stopped is not None
    assert stopped.current_reason == "clean_shutdown"
    assert stopped.clean_shutdown is True


async def test_planner_accounts_for_queued_predecessor_inside_window(
    hass: HomeAssistant,
) -> None:
    """Drop an automatic operation when earlier serial work consumes its full window."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    window_start = datetime.combine(
        date(2026, 7, 27), time(4), tzinfo=dt_util.DEFAULT_TIME_ZONE
    ).astimezone(UTC)
    predecessor = ManualIrrigationRequest(
        request_id="manual-predecessor",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=3_500,
        remaining_value=3_500,
        created_at=window_start.isoformat(),
        requested_start_at=window_start.isoformat(),
        expires_at=(window_start + timedelta(hours=2)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(predecessor,))

    report = await manager.async_plan_automatic(now=window_start)

    assert "automatic:zone-v2-runtime:2026-07-27" not in report["created_request_ids"]


async def test_cross_midnight_window_survives_replan_after_midnight(
    hass: HomeAssistant,
) -> None:
    """Consider the prior schedule day while its cross-midnight window remains open."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._stored_state = replace(manager._stored_state, manual_requests=())
    manager._zone_configs[0].data["weekly_schedule"] = [
        {
            "weekday": weekday,
            "start": "22:00:00" if weekday == "monday" else None,
            "end": "00:30:00" if weekday == "monday" else None,
            "target": 600.0 if weekday == "monday" else None,
        }
        for weekday in (
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        )
    ]
    local_now = datetime.combine(date(2026, 7, 28), time(0, 10), tzinfo=dt_util.DEFAULT_TIME_ZONE)

    report = await manager.async_plan_automatic(now=local_now.astimezone(UTC))

    assert "automatic:zone-v2-runtime:2026-07-27" in report["created_request_ids"]


async def test_startup_recovery_accounts_persisted_meter_baseline_and_runtime(
    hass: HomeAssistant,
) -> None:
    """Recover measurable water and elapsed delivery from the durable checkpoint."""
    entry, zone = await _setup_v2_installation(hass, with_meter=True)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="recover-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at=(now - timedelta(seconds=30)).isoformat(),
        expires_at=(now + timedelta(minutes=5)).isoformat(),
        status="executing",
        execution_id="recover-execution",
    )
    execution = IrrigationExecutionState(
        execution_id="recover-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        status="watering",
        created_at=request.created_at,
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(execution,),
        active_execution=ActiveExecutionState(
            zone_id=zone.unique_id,
            zone_valve="switch.lawn",
            main_valve=None,
            meter_raw_baseline_liters=100,
            prepared_at=request.created_at,
            watering_started_at=(now - timedelta(seconds=20)).isoformat(),
            requested_duration_seconds=60,
            request_id=request.request_id,
            execution_id=execution.execution_id,
        ),
    )
    manager._meter.read_liters = AsyncMock(return_value=112)

    await manager._async_recover_interrupted_execution()

    recovered = manager._stored_state.irrigation_executions[-1]
    assert recovered.delivered_liters == 12
    assert recovered.delivered_duration_seconds == pytest.approx(20, abs=1)
    assert recovered.measurement_quality == "measured"
    assert manager._stored_state.installation_total_liters == 12
    assert any(
        event.request_id == request.request_id and event.new_reason == "cancelled"
        for event in manager._stored_state.dispatcher_diagnostic_history
    )


async def test_emergency_stop_blocks_open_command_even_without_lock(
    hass: HomeAssistant,
) -> None:
    """Use the emergency flag itself as the final actuation gate."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    manager._stored_state = replace(
        manager._stored_state,
        emergency_stop=True,
        installation_safety_lock=None,
    )

    with pytest.raises(HomeAssistantError, match="emergency stop"):
        await manager._async_authorize_actuator_command("switch.lawn", True)
    await manager._async_authorize_actuator_command("switch.lawn", False)


async def test_stale_pending_snapshot_is_cancelled_and_authorization_uses_snapshot(
    hass: HomeAssistant,
) -> None:
    """Never redirect an accepted order or its permission check to newly edited valves."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="stale-snapshot",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.old_lawn",
        main_valve="switch.old_main",
        target_type="duration",
        target_value=10,
        remaining_value=10,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))

    assert manager.manual_control_entity_ids(request_ids=(request.request_id,)) == (
        "switch.old_lawn",
        "switch.old_main",
    )
    await manager._async_cancel_stale_pending_snapshots()
    assert manager._request(request.request_id).status == "cancelled"
    diagnostic_events = [
        event
        for event in manager._stored_state.dispatcher_diagnostic_history
        if event.request_id == request.request_id
    ]
    assert [event.new_reason for event in diagnostic_events[-2:]] == [
        "actuator_snapshot_mismatch",
        "cancelled",
    ]
    assert diagnostic_events[-2].locks == {"actuator_snapshot_mismatch": True}
