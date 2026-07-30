"""Authoritative v2 configuration behavior."""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta
from types import MappingProxyType
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigSubentry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_OFF
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
from custom_components.irrigation_manager.forecast import ForecastFetchResult, ForecastPeriod
from custom_components.irrigation_manager.manager import (
    IrrigationManager,
    _bounded_retry_delay,
    _with_automatic_cancellation_reason,
)
from custom_components.irrigation_manager.models import (
    AUTOMATIC_CANCELLATION_REASON_KEY,
    ActiveExecutionState,
    AutomaticCancellationReason,
    IrrigationExecutionState,
    IrrigationPortionState,
    ManualIrrigationRequest,
    PortionPolicySnapshot,
    StoredInstallationState,
)
from custom_components.irrigation_manager.scheduler import (
    select_manual_request as legacy_select_manual_request,
)
from custom_components.irrigation_manager.storage import IrrigationStore
from custom_components.irrigation_manager.water_balance import (
    WaterBalanceTargetResult,
    update_water_balance,
)


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

    assert entry.minor_version == 9
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
    assert entry.minor_version == 9
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


async def test_manual_request_snapshots_explicit_partial_irrigation_configuration(
    hass: HomeAssistant,
) -> None:
    """An accepted order keeps its optional limits despite later config changes."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "soak_module_enabled": True,
        },
        zone_overrides={
            "use_soak_module": True,
            "maximum_portion_target": 300.0,
            "minimum_soak_seconds": 600.0,
            "maximum_portions": 4,
            "maximum_lifetime_seconds": 7_200.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data["soak_module_enabled"] = True
    manager._zone_configs[0].data["use_soak_module"] = True

    result = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=1_200.0,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )

    request = manager._request(str(result["request_id"]))
    assert request is not None
    assert request.portion_policy == PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=300.0,
        minimum_soak_seconds=600.0,
        maximum_portions=4,
        maximum_lifetime_seconds=7_200.0,
    )
    manager._zone_configs[0].data["maximum_portion_target"] = 120.0
    assert request.portion_policy.maximum_portion_target == 300.0


async def test_manual_partial_irrigation_is_rejected_before_order_acceptance(
    hass: HomeAssistant,
) -> None:
    """Never persist a request whose immutable partial-delivery tail cannot fit."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "soak_module_enabled": True,
        },
        zone_overrides={
            "use_soak_module": True,
            "maximum_portion_target": 300.0,
            "minimum_soak_seconds": 600.0,
            "maximum_portions": 4,
            "maximum_lifetime_seconds": 7_200.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data["soak_module_enabled"] = True
    manager._zone_configs[0].data["use_soak_module"] = True
    requests_before = manager._stored_state.manual_requests

    with pytest.raises(HomeAssistantError, match="portion_limit_exceeded"):
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1_500.0,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )

    assert manager._stored_state.manual_requests == requests_before


async def test_automatic_partial_irrigation_infeasibility_is_reported_before_planning(
    hass: HomeAssistant,
) -> None:
    """Expose an infeasible partial target instead of creating a doomed order."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "soak_module_enabled": True,
        },
        zone_overrides={
            "use_soak_module": True,
            "maximum_portion_target": 300.0,
            "minimum_soak_seconds": 600.0,
            "maximum_portions": 1,
            "maximum_lifetime_seconds": 7_200.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data["soak_module_enabled"] = True
    manager._zone_configs[0].data["use_soak_module"] = True

    report = await manager.async_plan_automatic(now=datetime(2026, 7, 26, 12, tzinfo=UTC))

    assert report["created"] == 0
    assert report["not_plannable"] == [
        {
            "request_id": "automatic:zone-v2-runtime:2026-07-27",
            "zone_id": "zone-v2-runtime",
            "reason": "partial_irrigation_portion_limit_exceeded",
        },
        {
            "request_id": "automatic:zone-v2-runtime:2026-08-03",
            "zone_id": "zone-v2-runtime",
            "reason": "partial_irrigation_portion_limit_exceeded",
        },
    ]


async def test_zone_partial_irrigation_opt_in_requires_installation_availability(
    hass: HomeAssistant,
) -> None:
    """A zone opt-in alone keeps every new request on the legacy path."""
    entry, zone = await _setup_v2_installation(
        hass,
        zone_overrides={
            "maximum_portion_target": 300.0,
            "minimum_soak_seconds": 600.0,
            "maximum_portions": 4,
            "maximum_lifetime_seconds": 7_200.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._zone_configs[0].data["use_soak_module"] = True

    result = await manager.async_start_manual(
        zone_subentry_id=zone.subentry_id,
        duration_seconds=1_200.0,
        amount_liters=None,
        hard_time_limit_seconds=None,
        wait_for_completion=False,
    )

    request = manager._request(str(result["request_id"]))
    assert request is not None
    assert request.portion_policy is None


async def test_release_rollback_routes_new_opted_in_request_through_legacy_path(
    hass: HomeAssistant,
) -> None:
    """A release rollback blocks only new partial snapshots, without erasing opt-ins."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={"soak_module_enabled": True},
        zone_overrides={
            "use_soak_module": True,
            "maximum_portion_target": 300.0,
            "minimum_soak_seconds": 600.0,
            "maximum_portions": 4,
            "maximum_lifetime_seconds": 7_200.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data["soak_module_enabled"] = True
    manager._zone_configs[0].data["use_soak_module"] = True

    with patch(
        "custom_components.irrigation_manager.manager.integration_const."
        "PARTIAL_IRRIGATION_RELEASED",
        False,
    ):
        result = await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1_200.0,
            amount_liters=None,
            hard_time_limit_seconds=None,
            wait_for_completion=False,
        )

    request = manager._request(str(result["request_id"]))
    assert request is not None
    assert request.portion_policy is None
    assert manager._installation_data["soak_module_enabled"] is True
    assert manager._zone_configs[0].data["use_soak_module"] is True


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
        "weather_sources": {},
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
    assert entry.minor_version == 9
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
        "weather_sources": {},
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
        "use_weather_adjustment": False,
        "use_soil_moisture_feedback": False,
        "use_soak_module": False,
        "soil_moisture_assignments": [],
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

    assert entry.minor_version == 9
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


async def test_measured_water_balance_updates_only_todays_automatic_target(
    hass: HomeAssistant,
) -> None:
    """Persist daily weather progress while future dates retain their seasonal target."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_module_enabled": True,
            "weather_sources": {
                "reference_evapotranspiration": "sensor.reference_et",
                "precipitation_total": "sensor.rain_total",
            },
        },
        zone_overrides={
            "use_weather_adjustment": True,
            "watering_mode": "demand",
            "crop_factor": 1.0,
            "effective_rain_factor": 1.0,
            "demand_threshold_mm": 1.0,
            "maximum_deficit_mm": 100.0,
            "effective_application_rate_mm_h": 12.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data.update(
        {
            "weather_module_enabled": True,
            "weather_sources": {
                "reference_evapotranspiration": "sensor.reference_et",
                "precipitation_total": "sensor.rain_total",
            },
        },
    )
    manager._zone_configs[0].data.update(
        {
            "use_weather_adjustment": True,
            "watering_mode": "demand",
            "crop_factor": 1.0,
            "effective_rain_factor": 1.0,
            "demand_threshold_mm": 1.0,
            "maximum_deficit_mm": 100.0,
            "effective_application_rate_mm_h": 12.0,
        }
    )

    def observations(day: date, *, reference_et: float, rain_total: float) -> dict[str, object]:
        observed_at = datetime.combine(day, time(12), tzinfo=UTC).isoformat()
        return {
            "reference_evapotranspiration": {
                "source_entity_id": "sensor.reference_et",
                "quality": "available",
                "value": reference_et,
                "observed_at": observed_at,
            },
            "precipitation_total": {
                "source_entity_id": "sensor.rain_total",
                "quality": "available",
                "value": rain_total,
                "observed_at": observed_at,
            },
        }

    with patch(
        "custom_components.irrigation_manager.manager.observe_weather_sources",
        return_value=observations(date(2026, 7, 26), reference_et=4.0, rain_total=20.0),
    ):
        first = await manager.async_plan_automatic(now=datetime(2026, 7, 26, 8, tzinfo=UTC))

    initialized = manager._stored_state.zone_water_balances[zone.unique_id]
    assert initialized.ready_from_date == "2026-07-27"
    first_request = manager._request(first["created_request_ids"][0])
    assert first_request is not None
    assert first_request.target_value == 600.0
    assert first_request.resolved_inputs["water_balance"]["fallback_strategy"] == (
        "future_date_without_forecast"
    )

    with patch(
        "custom_components.irrigation_manager.manager.observe_weather_sources",
        return_value=observations(date(2026, 7, 27), reference_et=3.0, rain_total=21.0),
    ):
        await manager.async_plan_automatic(now=datetime(2026, 7, 27, 8, tzinfo=UTC))

    current = manager._request(f"automatic:{zone.unique_id}:2026-07-27")
    future = manager._request(f"automatic:{zone.unique_id}:2026-08-03")
    assert current is not None
    assert future is not None
    assert current.target_value == 2400.0
    water_balance = current.resolved_inputs["water_balance"]
    assert water_balance["quality"] == "valid"
    assert water_balance["fallback_strategy"] == "none"
    assert water_balance["opening_deficit_mm"] == 6.0
    assert water_balance["closing_deficit_mm"] == 8.0
    assert water_balance["reference_evapotranspiration_mm"] == 3.0
    assert water_balance["measured_precipitation_mm"] == 1.0
    assert water_balance["effective_target"] == 2400.0
    assert water_balance["crop_factor"] == 1.0
    assert water_balance["reference_et_source_entity_id"] == "sensor.reference_et"
    assert water_balance["precipitation_source_entity_id"] == "sensor.rain_total"
    assert future.target_value == 600.0
    assert future.resolved_inputs["water_balance"]["fallback_strategy"] == (
        "future_date_without_forecast"
    )
    for key in (
        "reference_et_source_entity_id",
        "reference_et_observed_at",
        "precipitation_source_entity_id",
        "precipitation_observed_at",
        "opening_deficit_mm",
        "closing_deficit_mm",
        "reference_evapotranspiration_mm",
        "plant_evapotranspiration_mm",
        "measured_precipitation_mm",
        "effective_precipitation_mm",
        "effective_irrigation_mm",
    ):
        assert future.resolved_inputs["water_balance"][key] is None
    future_revision = future.revision

    with patch(
        "custom_components.irrigation_manager.manager.observe_weather_sources",
        return_value=observations(date(2026, 7, 27), reference_et=4.0, rain_total=22.0),
    ):
        await manager.async_plan_automatic(now=datetime(2026, 7, 27, 9, tzinfo=UTC))

    stable_future = manager._request(f"automatic:{zone.unique_id}:2026-08-03")
    assert stable_future is not None
    assert stable_future.revision == future_revision
    balance_diagnostics = manager.diagnostics_state_decisions()["water_balances"]
    assert balance_diagnostics[zone.unique_id]["latest_day"]["closing_deficit_mm"] == 8.0
    assert "source_entity_id" not in balance_diagnostics[zone.unique_id]["latest_day"]

    manager._zone_configs[0].data["weekly_schedule"][1].update(
        {"start": "04:00:00", "end": "05:00:00", "target": 600.0}
    )
    with patch(
        "custom_components.irrigation_manager.manager.observe_weather_sources",
        return_value=observations(date(2026, 7, 28), reference_et=0.0, rain_total=40.0),
    ):
        skipped = await manager.async_plan_automatic(now=datetime(2026, 7, 28, 8, tzinfo=UTC))

    assert manager._request(f"automatic:{zone.unique_id}:2026-07-28") is None
    assert skipped["not_plannable"] == [
        {
            "request_id": f"automatic:{zone.unique_id}:2026-07-28",
            "zone_id": zone.unique_id,
            "reason": "water_deficit_below_threshold",
        }
    ]


async def test_water_balance_initialization_uses_todays_weekday_override(
    hass: HomeAssistant,
) -> None:
    """Initialize from today's effective scheduled target, not the common baseline."""
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_module_enabled": True,
            "weather_sources": {
                "reference_evapotranspiration": "sensor.reference_et",
                "precipitation_total": "sensor.rain_total",
            },
        },
        zone_overrides={
            "base_target": 600.0,
            "use_weather_adjustment": True,
            "watering_mode": "demand",
            "crop_factor": 1.0,
            "effective_rain_factor": 1.0,
            "demand_threshold_mm": 1.0,
            "maximum_deficit_mm": 100.0,
            "effective_application_rate_mm_h": 12.0,
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data.update(
        {
            "weather_module_enabled": True,
            "weather_sources": {
                "reference_evapotranspiration": "sensor.reference_et",
                "precipitation_total": "sensor.rain_total",
            },
        }
    )
    manager._zone_configs[0].data.update(
        {
            "base_target": 600.0,
            "use_weather_adjustment": True,
            "watering_mode": "demand",
            "crop_factor": 1.0,
            "effective_rain_factor": 1.0,
            "demand_threshold_mm": 1.0,
            "maximum_deficit_mm": 100.0,
            "effective_application_rate_mm_h": 12.0,
        }
    )
    manager._zone_configs[0].data["weekly_schedule"][0]["target"] = 1800.0
    observations = {
        "reference_evapotranspiration": {
            "source_entity_id": "sensor.reference_et",
            "quality": "available",
            "value": 4.0,
            "observed_at": "2026-07-27T12:00:00+00:00",
        },
        "precipitation_total": {
            "source_entity_id": "sensor.rain_total",
            "quality": "available",
            "value": 20.0,
            "observed_at": "2026-07-27T12:00:00+00:00",
        },
    }

    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.update_water_balance",
            wraps=update_water_balance,
        ) as balance_update,
    ):
        await manager.async_plan_automatic(now=datetime(2026, 7, 27, 3, tzinfo=UTC))

    balance_update.assert_called_once()
    assert balance_update.call_args.kwargs["seasonal_base_target"] == 1800.0


async def test_cross_midnight_execution_is_split_between_local_days(
    hass: HomeAssistant,
) -> None:
    """Allocate runtime exactly and measured liters proportionally at local midnight."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    execution = IrrigationExecutionState(
        execution_id="cross-midnight",
        request_id="request-cross-midnight",
        zone_id=zone.unique_id,
        target_type="volume",
        target_value=20.0,
        remaining_value=0.0,
        status="completed",
        created_at="2026-07-28T23:40:00+02:00",
        delivered_liters=20.0,
        delivered_duration_seconds=1200.0,
        watering_started_at="2026-07-28T23:50:00+02:00",
        watering_ended_at="2026-07-29T00:10:00+02:00",
        ended_at="2026-07-29T00:10:00+02:00",
        measurement_quality="measured",
    )
    manager._stored_state = replace(
        manager._stored_state,
        irrigation_executions=(execution,),
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Zurich")):
        contributions = manager._irrigation_contributions(
            zone_id=zone.unique_id,
            local_date=date(2026, 7, 29),
        )

    assert [(item.local_date, item.delivered_duration_seconds) for item in contributions] == [
        (date(2026, 7, 28), 600.0),
        (date(2026, 7, 29), 600.0),
    ]
    assert [item.delivered_liters for item in contributions] == [10.0, 10.0]
    assert all(item.warnings == ("irrigation_split_across_midnight",) for item in contributions)


async def test_execution_without_persisted_valve_times_is_marked_unreliable(
    hass: HomeAssistant,
) -> None:
    """Startup recovery must not invent a calendar allocation from finalization time."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    execution = IrrigationExecutionState(
        execution_id="recovered-without-times",
        request_id="request-recovered-without-times",
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=600.0,
        remaining_value=0.0,
        status="interrupted",
        created_at="2026-07-28T23:40:00+02:00",
        delivered_duration_seconds=600.0,
        ended_at="2026-07-29T00:10:00+02:00",
        measurement_quality="unavailable",
    )
    manager._stored_state = replace(
        manager._stored_state,
        irrigation_executions=(execution,),
    )

    contributions = manager._irrigation_contributions(
        zone_id=zone.unique_id,
        local_date=date(2026, 7, 29),
    )

    assert len(contributions) == 1
    assert contributions[0].allocation_quality == "unreliable"
    assert contributions[0].warnings == ("irrigation_timing_unavailable",)


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


async def test_weather_source_only_change_does_not_reload_runtime(
    hass: HomeAssistant,
) -> None:
    """Keep source assignment observational until weather correction is released."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    requests_before = manager._stored_state.manual_requests

    with patch.object(manager, "async_request_config_reload", new_callable=AsyncMock) as reload:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                "weather_sources": {"air_temperature": "sensor.outdoor_temperature"},
            },
        )
        await hass.async_block_till_done()

        reload.assert_not_awaited()
        assert manager._stored_state.manual_requests == requests_before
        assert manager._config_reload_pending is False
        assert manager._installation_data["weather_sources"] == {
            "air_temperature": "sensor.outdoor_temperature"
        }

        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, "seasonal_module_enabled": True},
        )
        await hass.async_block_till_done()

        reload.assert_awaited_once_with()


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


async def test_legacy_dispatch_golden_trace_stays_on_the_single_delivery_path(
    hass: HomeAssistant,
) -> None:
    """Freeze selection, atomic stores, executor handoff and terminal legacy result."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    trace: list[tuple[object, ...]] = []
    last_store_marker: tuple[object, ...] | None = None
    original_save = manager._store.async_save

    async def traced_save(state: StoredInstallationState) -> None:
        nonlocal last_store_marker
        manual = next(
            (request for request in reversed(state.manual_requests) if request.source == "manual"),
            None,
        )
        if manual is not None:
            execution = next(
                (
                    item
                    for item in state.irrigation_executions
                    if item.execution_id == manual.execution_id
                ),
                None,
            )
            marker = (
                "store",
                manual.status,
                execution.status if execution is not None else None,
                state.active_execution is not None,
                manual.portion_policy,
            )
            if marker != last_store_marker:
                trace.append(marker)
                last_store_marker = marker
        await original_save(state)

    def traced_select(*, now, requests):
        selected = legacy_select_manual_request(now=now, requests=requests)
        if selected is not None:
            marker = (
                "select",
                selected.status,
                selected.target_type,
                selected.target_value,
                selected.portion_policy,
            )
            if marker not in trace:
                trace.append(marker)
        return selected

    async def traced_execute(request) -> ExecutionResult:
        active = manager._stored_state.active_execution
        trace.append(
            (
                "executor",
                request.duration_seconds,
                request.amount_liters,
                active is not None,
                active.portion_id if active is not None else None,
            )
        )
        return ExecutionResult(
            zone_id=zone.unique_id,
            delivered_liters=0.0,
            duration_seconds=0.001,
        )

    with (
        patch.object(manager._store, "async_save", side_effect=traced_save),
        patch(
            "custom_components.irrigation_manager.manager.select_manual_request",
            side_effect=traced_select,
        ),
    ):
        manager._executor.execute = traced_execute
        manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
        await manager.async_start_manual(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=0.001,
            amount_liters=None,
            hard_time_limit_seconds=None,
        )

    assert trace == [
        ("store", "pending", None, False, None),
        ("select", "pending", "duration", 0.001, None),
        ("store", "executing", "watering", True, None),
        ("executor", 0.001, None, True, None),
        ("store", "completed", "completed", False, None),
    ]


async def test_released_partial_irrigation_executes_one_bounded_portion_at_a_time(
    hass: HomeAssistant,
) -> None:
    """A released process persists and settles two portions under one durable order."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=0.001,
        minimum_soak_seconds=0.001,
        maximum_portions=2,
        maximum_lifetime_seconds=60.0,
    )
    request = ManualIrrigationRequest(
        request_id="partial-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=0.002,
        remaining_value=0.002,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=60)).isoformat(),
        delivery_runtime_limit_seconds=0.002,
        operation_deadline_at=(now + timedelta(seconds=60)).isoformat(),
        portion_policy=policy,
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    executed_targets: list[float] = []

    async def execute_portion(execution_request) -> ExecutionResult:
        assert execution_request.duration_seconds is not None
        durable = await IrrigationStore(hass, entry.entry_id).async_load()
        active = durable.active_execution
        assert active is not None
        assert active.portion_id is not None
        durable_portion = next(
            portion
            for portion in durable.irrigation_portions
            if portion.portion_id == active.portion_id
        )
        assert durable_portion.status == "prepared"
        durable_process = next(
            process
            for process in durable.irrigation_executions
            if process.execution_id == active.execution_id
        )
        assert durable_process.status == "watering"
        executed_targets.append(execution_request.duration_seconds)
        if execution_request.on_zone_opening is not None:
            await execution_request.on_zone_opening()
        if execution_request.on_zone_opened is not None:
            await execution_request.on_zone_opened()
        if execution_request.on_zone_closed is not None:
            await execution_request.on_zone_closed()
        return ExecutionResult(
            zone_id=zone.unique_id,
            delivered_liters=0.0,
            duration_seconds=execution_request.duration_seconds,
            measurement_quality="unavailable",
        )

    manager._executor.execute = execute_portion
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    manager._queue_event.set()
    async with asyncio.timeout(2):
        while manager.list_manual_requests()[0]["status"] != "completed":  # noqa: ASYNC110
            await asyncio.sleep(0.001)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert executed_targets == [0.001, 0.001]
    assert len(stored.manual_requests) == 1
    assert stored.manual_requests[0].status == "completed"
    assert len(stored.irrigation_executions) == 1
    assert stored.irrigation_executions[0].delivered_duration_seconds == pytest.approx(0.002)
    assert stored.irrigation_executions[0].status == "completed"
    assert [portion.status for portion in stored.irrigation_portions] == [
        "settled",
        "settled",
    ]
    assert [record.portion_id for record in stored.water_consumption_history] == []
    assert stored.active_execution is None


async def test_cancelling_partial_process_during_soak_is_terminal_without_hardware(
    hass: HomeAssistant,
) -> None:
    """Cancel the whole process during its hardware-free pause without another handoff."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-cancel-soak",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=30.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    handoffs = 0

    async def execute_first(execution_request) -> ExecutionResult:
        nonlocal handoffs
        handoffs += 1
        if execution_request.on_zone_opening is not None:
            await execution_request.on_zone_opening()
        if execution_request.on_zone_opened is not None:
            await execution_request.on_zone_opened()
        if execution_request.on_zone_closed is not None:
            await execution_request.on_zone_closed()
        return ExecutionResult(
            zone_id=zone.unique_id,
            delivered_liters=0.0,
            duration_seconds=1.0,
            measurement_quality="unavailable",
        )

    manager._executor.execute = execute_first
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    manager._queue_event.set()
    async with asyncio.timeout(2):
        while not (  # noqa: ASYNC110
            manager.list_irrigation_executions()
            and manager.list_irrigation_executions()[0]["status"] == "soaking"
        ):
            await asyncio.sleep(0.001)

    await manager.async_cancel_request(request.request_id)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert handoffs == 1
    assert stored.manual_requests[0].status == "cancelled"
    assert stored.irrigation_executions[0].status == "cancelled"
    assert stored.irrigation_executions[0].result == "user_requested"
    assert stored.active_execution is None


async def test_disabling_zone_during_soak_cancels_process_before_resumption(
    hass: HomeAssistant,
) -> None:
    """Revoking a zone release owns the whole paused process, not only hardware."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-zone-disable-soak",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=30.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    handoffs = 0

    async def execute_first(execution_request) -> ExecutionResult:
        nonlocal handoffs
        handoffs += 1
        if execution_request.on_zone_opening is not None:
            await execution_request.on_zone_opening()
        if execution_request.on_zone_opened is not None:
            await execution_request.on_zone_opened()
        if execution_request.on_zone_closed is not None:
            await execution_request.on_zone_closed()
        return ExecutionResult(
            zone_id=zone.unique_id,
            delivered_liters=0.0,
            duration_seconds=1.0,
            measurement_quality="unavailable",
        )

    manager._executor.execute = execute_first
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    manager._queue_event.set()
    async with asyncio.timeout(2):
        while not (  # noqa: ASYNC110
            manager.list_irrigation_executions()
            and manager.list_irrigation_executions()[0]["status"] == "soaking"
        ):
            await asyncio.sleep(0.001)

    await manager.async_set_zone_operation(
        zone_subentry_id=zone.subentry_id,
        enabled=False,
    )

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert handoffs == 1
    assert stored.manual_requests[0].status == "cancelled"
    assert stored.irrigation_executions[0].status == "cancelled"
    assert stored.irrigation_executions[0].result == "zone_disabled"
    assert stored.active_execution is None


async def test_active_partial_cancellation_is_durable_before_executor_cancel(
    hass: HomeAssistant,
) -> None:
    """Persist whole-process cancellation intent before interrupting hydraulic work."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-cancel-active",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    started = asyncio.Event()
    cancellation_was_durable = False

    async def execute_until_cancel(execution_request) -> ExecutionResult:
        nonlocal cancellation_was_durable
        if execution_request.on_zone_opening is not None:
            await execution_request.on_zone_opening()
        if execution_request.on_zone_opened is not None:
            await execution_request.on_zone_opened()
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            durable = await IrrigationStore(hass, entry.entry_id).async_load()
            process = durable.irrigation_executions[0]
            cancellation_was_durable = (
                process.cancellation_requested
                and process.cancellation_reason == "user_requested"
                and durable.active_execution is not None
            )
            if execution_request.on_zone_closed is not None:
                await execution_request.on_zone_closed()
            return ExecutionResult(
                zone_id=zone.unique_id,
                delivered_liters=0.0,
                duration_seconds=0.25,
                stopped=True,
                measurement_quality="unavailable",
            )

    manager._executor.execute = execute_until_cancel
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    manager._queue_event.set()
    await started.wait()

    await manager.async_cancel_request(request.request_id)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert cancellation_was_durable is True
    assert stored.manual_requests[0].status == "cancelled"
    assert stored.irrigation_executions[0].status == "cancelled"
    assert stored.irrigation_executions[0].delivered_duration_seconds == 0.25
    assert stored.active_execution is None


async def test_release_rollback_completes_a_persisted_partial_request(
    hass: HomeAssistant,
) -> None:
    """Disabling new acceptance must not strand immutable durable partial work."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-gate-off",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    executed_targets: list[float] = []

    async def execute_persisted_portion(execution_request) -> ExecutionResult:
        assert execution_request.duration_seconds is not None
        executed_targets.append(execution_request.duration_seconds)
        if execution_request.on_zone_opening is not None:
            await execution_request.on_zone_opening()
        if execution_request.on_zone_opened is not None:
            await execution_request.on_zone_opened()
        if execution_request.on_zone_closed is not None:
            await execution_request.on_zone_closed()
        return ExecutionResult(
            zone_id=execution_request.zone_id,
            delivered_liters=0.0,
            duration_seconds=execution_request.duration_seconds,
            measurement_quality="unavailable",
        )

    manager._executor.execute = execute_persisted_portion
    with patch(
        "custom_components.irrigation_manager.manager.integration_const."
        "PARTIAL_IRRIGATION_RELEASED",
        False,
    ):
        dispatcher = hass.async_create_task(manager._async_dispatch_requests())
        manager._dispatcher_task = dispatcher
        manager._queue_event.set()
        async with asyncio.timeout(2):
            while manager.list_manual_requests()[0]["status"] != "completed":  # noqa: ASYNC110
                await asyncio.sleep(0.001)
        dispatcher.cancel()
        await asyncio.gather(dispatcher, return_exceptions=True)

    assert executed_targets == [1.0, 1.0]
    assert manager.list_manual_requests()[0]["status"] == "completed"


async def test_partial_start_that_cannot_fit_is_persisted_fail_closed_without_actuation(
    hass: HomeAssistant,
) -> None:
    """Interpret a non-actuating core transition instead of losing its evidence."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-window-not-fit",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(seconds=12.5)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    executor_called = asyncio.Event()

    async def must_not_execute(execution_request) -> ExecutionResult:
        executor_called.set()
        return ExecutionResult(
            zone_id=execution_request.zone_id,
            delivered_liters=0.0,
            duration_seconds=0.0,
            measurement_quality="unavailable",
        )

    manager._executor.execute = must_not_execute
    dispatcher = hass.async_create_task(manager._async_dispatch_requests())
    manager._dispatcher_task = dispatcher
    manager._queue_event.set()
    async with asyncio.timeout(2):
        while manager.list_manual_requests()[0]["status"] != "cancelled":  # noqa: ASYNC110
            await asyncio.sleep(0.001)
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert executor_called.is_set() is False
    assert stored.active_execution is None
    assert stored.installation_safety_lock is None
    assert stored.irrigation_executions[0].status == "failed"
    assert stored.irrigation_executions[0].result == "process_window_not_fit"


async def test_partial_prepare_commit_failure_never_reaches_executor(
    hass: HomeAssistant,
) -> None:
    """A failed durable prepare is a hard barrier before hydraulic handoff."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-prepare-fault",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    original_save = manager._store.async_save
    prepare_failed = asyncio.Event()
    executor_called = asyncio.Event()

    async def fail_only_prepare(state) -> None:
        if state.active_execution is not None:
            prepare_failed.set()
            raise RuntimeError("injected prepare commit failure")
        await original_save(state)

    async def must_not_execute(execution_request) -> ExecutionResult:
        executor_called.set()
        return ExecutionResult(
            zone_id=execution_request.zone_id,
            delivered_liters=0.0,
            duration_seconds=0.0,
            measurement_quality="unavailable",
        )

    manager._store.async_save = fail_only_prepare
    manager._executor.execute = must_not_execute
    dispatcher = hass.async_create_task(manager._async_dispatch_requests())
    manager._dispatcher_task = dispatcher
    manager._queue_event.set()
    async with asyncio.timeout(2):
        await prepare_failed.wait()
        while manager.list_manual_requests()[0]["status"] != "cancelled":  # noqa: ASYNC110
            await asyncio.sleep(0.001)
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert executor_called.is_set() is False
    assert stored.active_execution is None
    assert stored.manual_requests[0].status == "cancelled"
    assert stored.installation_safety_lock == "injected prepare commit failure"


async def test_partial_executor_fault_after_commit_retires_prepared_portion(
    hass: HomeAssistant,
) -> None:
    """Unknown hardware state after handoff cannot leave an open portion record."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-post-commit-fault",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=2.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    durable_prepare_seen = False

    async def fail_before_opening(execution_request) -> ExecutionResult:
        nonlocal durable_prepare_seen
        durable = await IrrigationStore(hass, entry.entry_id).async_load()
        durable_prepare_seen = (
            durable.active_execution is not None
            and durable.irrigation_portions[0].status == "prepared"
        )
        raise RuntimeError("injected executor fault before opening")

    manager._executor.execute = fail_before_opening
    dispatcher = hass.async_create_task(manager._async_dispatch_requests())
    manager._dispatcher_task = dispatcher
    manager._queue_event.set()
    async with asyncio.timeout(2):
        while manager.list_manual_requests()[0]["status"] != "cancelled":  # noqa: ASYNC110
            await asyncio.sleep(0.001)
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert durable_prepare_seen is True
    assert stored.active_execution is None
    assert stored.irrigation_executions[0].status == "failed"
    assert stored.irrigation_portions[0].status == "interrupted"
    assert stored.installation_safety_lock == "injected executor fault before opening"


async def test_partial_open_is_reauthorized_after_prepare_commit(
    hass: HomeAssistant,
) -> None:
    """A durable lock raised after prepare still prevents the first open command."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-late-lock",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=1.0,
        remaining_value=1.0,
        created_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=1.0,
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=1,
            maximum_lifetime_seconds=120.0,
        ),
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=(request,))
    prepared = asyncio.Event()
    allow_open_check = asyncio.Event()
    open_authorized = False

    async def check_authorization_after_lock(execution_request) -> ExecutionResult:
        nonlocal open_authorized
        prepared.set()
        await allow_open_check.wait()
        assert execution_request.on_actuator_command is not None
        await execution_request.on_actuator_command("switch.lawn", True)
        open_authorized = True
        raise AssertionError("The durable safety lock should have denied opening")

    manager._executor.execute = check_authorization_after_lock
    dispatcher = hass.async_create_task(manager._async_dispatch_requests())
    manager._dispatcher_task = dispatcher
    manager._queue_event.set()
    await prepared.wait()
    async with manager._command_lock:
        manager._stored_state = replace(
            manager._stored_state,
            installation_safety_lock="injected post-prepare lock",
            installation_safety_lock_at=datetime.now(UTC).isoformat(),
        )
        await manager._store.async_save(manager._stored_state)
    allow_open_check.set()
    async with asyncio.timeout(2):
        while manager.list_manual_requests()[0]["status"] != "cancelled":  # noqa: ASYNC110
            await asyncio.sleep(0.001)
    dispatcher.cancel()
    await asyncio.gather(dispatcher, return_exceptions=True)

    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    assert open_authorized is False
    assert stored.active_execution is None
    assert stored.irrigation_portions[0].status == "interrupted"
    assert stored.installation_safety_lock is not None


async def test_due_soaking_process_does_not_create_zero_timeout_busy_loop(
    hass: HomeAssistant,
) -> None:
    """A due continuation is dispatched or sleeps for an external state change."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=1.0,
        minimum_soak_seconds=1.0,
        maximum_portions=2,
        maximum_lifetime_seconds=120.0,
    )
    request = ManualIrrigationRequest(
        request_id="partial-due-pause",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=1.0,
        created_at=(now - timedelta(seconds=2)).isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        status="executing",
        execution_id="partial-due-execution",
        portion_policy=policy,
    )
    process = IrrigationExecutionState(
        execution_id="partial-due-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=2.0,
        remaining_value=1.0,
        status="soaking",
        created_at=(now - timedelta(seconds=2)).isoformat(),
        operation_deadline_at=request.operation_deadline_at,
        delivery_runtime_limit_seconds=2.0,
        portion_policy=policy,
        process_started_at=(now - timedelta(seconds=2)).isoformat(),
        process_deadline_at=request.operation_deadline_at,
        hydraulic_overhead_seconds_per_portion=5.0,
        next_portion_at=(now - timedelta(milliseconds=1)).isoformat(),
        next_portion_sequence=2,
        completed_portion_count=1,
        delivered_duration_seconds=1.0,
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(process,),
    )

    timeout = manager._seconds_until_next_request_change()

    assert timeout is not None
    assert timeout > 1.0


async def test_automatic_release_without_stop_does_not_block_started_process(
    hass: HomeAssistant,
) -> None:
    """Automation eligibility is a start gate, not a renewed continuation gate."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "automation_enabled": False,
        },
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    request = ManualIrrigationRequest(
        request_id="partial-automatic-continuation",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=2.0,
        remaining_value=1.0,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(minutes=2)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=2)).isoformat(),
        delivery_runtime_limit_seconds=2.0,
        status="executing",
        source="automatic",
        execution_id="partial-automatic-execution",
        portion_policy=PortionPolicySnapshot(
            target_type="duration",
            maximum_portion_target=1.0,
            minimum_soak_seconds=1.0,
            maximum_portions=2,
            maximum_lifetime_seconds=120.0,
        ),
    )

    start_decision = manager._dispatch_decision(request, now=now)
    continuation_decision = manager._dispatch_decision(
        request,
        now=now,
        continuing_execution=True,
    )

    assert start_decision.reason.value == "automation_disabled"
    assert continuation_decision.reason.value == "ready"


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

    assert entry.minor_version == 9
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
        "weather_sources",
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


async def test_diagnostics_normalize_weather_sources_without_changing_planning(
    hass: HomeAssistant,
) -> None:
    """Expose canonical source observations while weather correction stays dormant."""
    hass.states.async_set(
        "sensor.outdoor_temperature",
        "68",
        {
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°F",
        },
    )
    hass.states.async_set(
        "sensor.outdoor_humidity",
        "101",
        {
            "device_class": "humidity",
            "state_class": "measurement",
            "unit_of_measurement": "%",
        },
    )
    hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": 20,
            "temperature_unit": "°C",
            "humidity": 45,
            "wind_speed": 18,
            "wind_speed_unit": "km/h",
            "supported_features": 3,
        },
    )
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_module_enabled": False,
            "weather_sources": {
                "air_temperature": "sensor.outdoor_temperature",
                "relative_humidity": "sensor.outdoor_humidity",
                "wind_speed": "weather.forecast_home",
                "forecast": "weather.forecast_home",
            },
        },
    )

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    weather = diagnostics["weather_sources"]
    assert weather["weather_correction_enabled"] is False
    observations = weather["observations"]
    temperature = observations["air_temperature"]
    assert temperature["quality"] == "available"
    assert temperature["reason"] is None
    assert temperature["value"] == 20.0
    assert temperature["unit"] == "°C"
    assert observations["relative_humidity"]["quality"] == "implausible"
    assert observations["relative_humidity"]["reason"] == "outside_plausible_range"
    assert observations["wind_speed"]["value"] == 5.0
    assert observations["wind_speed"]["unit"] == "m/s"
    assert observations["forecast"]["quality"] == "available"
    assert observations["forecast"]["supported_forecast_types"] == ["daily", "hourly"]
    assert observations["solar_irradiance"]["quality"] == "not_configured"

    manager = entry.runtime_data.manager
    assert manager._installation_data["weather_module_enabled"] is False
    assert all(
        "water_balance" not in request.resolved_inputs
        for request in manager._stored_state.manual_requests
        if request.source == "automatic"
    )


async def test_weather_diagnostics_apply_role_contracts_and_cross_checks(
    hass: HomeAssistant,
) -> None:
    """Normalize supported units and reject a dew point above air temperature."""
    hass.states.async_set(
        "sensor.rain_total",
        "2",
        {
            "device_class": "precipitation",
            "state_class": "total_increasing",
            "unit_of_measurement": "in",
        },
    )
    hass.states.async_set(
        "sensor.daily_et",
        "0.25",
        {
            "state_class": "total",
            "unit_of_measurement": "in/d",
        },
    )
    hass.states.async_set(
        "sensor.solar_radiation",
        "1",
        {
            "device_class": "irradiance",
            "state_class": "measurement",
            "unit_of_measurement": "BTU/(h⋅ft²)",
        },
    )
    hass.states.async_set(
        "weather.forecast_home",
        "sunny",
        {
            "temperature": 20,
            "dew_point": 23,
            "temperature_unit": "°C",
            "supported_features": 1,
        },
    )
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_sources": {
                "precipitation_total": "sensor.rain_total",
                "precipitation_rate": "sensor.missing_rain_rate",
                "reference_evapotranspiration": "sensor.daily_et",
                "air_temperature": "weather.forecast_home",
                "dew_point": "weather.forecast_home",
                "solar_irradiance": "sensor.solar_radiation",
            },
        },
    )

    observations = (await async_get_config_entry_diagnostics(hass, entry))["weather_sources"][
        "observations"
    ]

    assert observations["precipitation_total"]["value"] == 50.8
    assert observations["precipitation_total"]["unit"] == "mm"
    assert observations["reference_evapotranspiration"]["value"] == 6.35
    assert observations["reference_evapotranspiration"]["unit"] == "mm/d"
    assert observations["solar_irradiance"]["value"] == pytest.approx(3.15459075)
    assert observations["solar_irradiance"]["unit"] == "W/m²"
    assert observations["precipitation_rate"]["quality"] == "unavailable"
    assert observations["precipitation_rate"]["reason"] == "entity_not_found"
    assert observations["dew_point"]["quality"] == "implausible"
    assert observations["dew_point"]["reason"] == "dew_point_above_temperature"


async def test_weather_diagnostics_mark_old_source_reports_stale(
    hass: HomeAssistant,
) -> None:
    """Use the source report timestamp and the role-specific maximum age."""
    hass.states.async_set(
        "sensor.outdoor_temperature",
        "20",
        {
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°C",
        },
    )
    state = hass.states.get("sensor.outdoor_temperature")
    assert state is not None
    entry, _zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_sources": {
                "air_temperature": "sensor.outdoor_temperature",
            }
        },
    )

    with patch("custom_components.irrigation_manager.weather_sources.datetime") as clock:
        clock.now.return_value = state.last_reported + timedelta(hours=2, seconds=1)
        observation = (await async_get_config_entry_diagnostics(hass, entry))["weather_sources"][
            "observations"
        ]["air_temperature"]

    assert observation["quality"] == "stale"
    assert observation["reason"] == "source_stale"
    assert observation["age_seconds"] == 7201.0


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


async def test_restart_discards_duplicate_pending_copy_of_terminal_automatic_request(
    hass: HomeAssistant,
) -> None:
    """Never re-execute a deterministic automatic ID already recorded as terminal."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    pending = ManualIrrigationRequest(
        request_id=f"automatic:{zone.unique_id}:{now.date().isoformat()}",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        requested_start_at=(now - timedelta(seconds=1)).isoformat(),
        expires_at=(now + timedelta(minutes=10)).isoformat(),
        automatic_window_end=(now + timedelta(minutes=10)).isoformat(),
        operation_deadline_at=(now + timedelta(minutes=10)).isoformat(),
        source="automatic",
    )
    terminal = replace(pending, status="completed", revision=2)
    raw_state = manager._stored_state.as_dict()
    raw_state["manual_requests"] = [terminal.as_dict(), pending.as_dict()]
    manager._stored_state = StoredInstallationState.from_dict(raw_state)
    manager._dispatcher_task = entry.async_create_background_task(
        hass,
        manager._async_dispatch_requests(),
        "duplicate automatic request regression",
    )
    manager._queue_event.set()
    await asyncio.sleep(0.05)

    requests = manager.list_manual_requests()
    assert len(requests) == 1
    assert requests[0]["status"] == "completed"
    assert manager.diagnostics_state_decisions()["dispatcher"]["current_reason"] != (
        "dispatcher_error"
    )
    assert hass.states.get("switch.lawn").state == STATE_OFF


async def test_restart_replans_future_orders_cancelled_by_automation_release(
    hass: HomeAssistant,
) -> None:
    """Recreate scheduled work after automation is disabled, restarted, and enabled."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    request_id = f"automatic:{zone.unique_id}:2026-07-27"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        manual_requests=(),
    )

    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")),
        patch.object(dt_util, "now", return_value=now),
    ):
        initial = await manager.async_plan_automatic(now=now)
        assert request_id in initial["created_request_ids"]

        await manager.async_set_installation_automation(
            enabled=False,
            stop_active=False,
        )
        cancelled = manager._request(request_id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"

        manager._stored_state = StoredInstallationState.from_dict(manager._stored_state.as_dict())
        enabled = await manager.async_set_installation_automation(
            enabled=True,
            stop_active=False,
        )

    assert enabled["replan"] is not None
    assert request_id in enabled["replan"]["created_request_ids"]
    replanned = manager._request(request_id)
    assert replanned is not None
    assert replanned.status == "pending"
    assert (
        sum(request.request_id == request_id for request in manager._stored_state.manual_requests)
        == 1
    )


async def test_explicitly_cancelled_automatic_order_is_not_replanned(
    hass: HomeAssistant,
) -> None:
    """Respect a user's withdrawal of one scheduled automatic order."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    request_id = f"automatic:{zone.unique_id}:2026-07-27"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        manual_requests=(),
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")):
        initial = await manager.async_plan_automatic(now=now)
        assert request_id in initial["created_request_ids"]

        await manager.async_cancel_request(request_id)
        replanned = await manager.async_plan_automatic(now=now)

    assert request_id not in replanned["created_request_ids"]
    cancelled = manager._request(request_id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"
    assert (
        sum(request.request_id == request_id for request in manager._stored_state.manual_requests)
        == 1
    )


@pytest.mark.parametrize(
    ("terminal_status", "reason"),
    [
        ("expired", None),
        ("cancelled", AutomaticCancellationReason.EXECUTION_FAILED),
        ("cancelled", AutomaticCancellationReason.RESTART_INTERRUPTED),
    ],
    ids=("expired", "execution-failed", "restart-interrupted"),
)
async def test_terminal_automatic_order_survives_restart_without_replanning(
    hass: HomeAssistant,
    terminal_status: str,
    reason: AutomaticCancellationReason | None,
) -> None:
    """Keep every non-user terminal outcome final across persistence and planning."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    request_id = f"automatic:{zone.unique_id}:2026-07-27"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        manual_requests=(),
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")):
        await manager.async_plan_automatic(now=now)
        pending = manager._request(request_id)
        assert pending is not None
        terminal = replace(
            pending,
            status=terminal_status,
            revision=pending.revision + 1,
        )
        if reason is not None:
            terminal = _with_automatic_cancellation_reason(terminal, reason)
        manager._stored_state = replace(
            manager._stored_state,
            manual_requests=(terminal,),
        )
        manager._stored_state = StoredInstallationState.from_dict(manager._stored_state.as_dict())

        replanned = await manager.async_plan_automatic(now=now)

    assert request_id not in replanned["created_request_ids"]
    persisted = manager._request(request_id)
    assert persisted is not None
    assert persisted.status == terminal_status
    assert (
        sum(request.request_id == request_id for request in manager._stored_state.manual_requests)
        == 1
    )


@pytest.mark.parametrize(
    "legacy_reason",
    [None, "misspelled_future_reason"],
    ids=["missing", "unknown"],
)
async def test_unclassified_legacy_cancellation_is_not_replanned_implicitly(
    hass: HomeAssistant, legacy_reason: str | None
) -> None:
    """Fail closed when pre-rc28 storage cannot prove why an order was cancelled."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    request_id = f"automatic:{zone.unique_id}:2026-07-27"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        manual_requests=(),
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")):
        await manager.async_plan_automatic(now=now)
        pending = manager._request(request_id)
        assert pending is not None
        legacy_cancelled = replace(
            pending,
            status="cancelled",
            resolved_inputs={
                **pending.resolved_inputs,
                **(
                    {AUTOMATIC_CANCELLATION_REASON_KEY: legacy_reason}
                    if legacy_reason is not None
                    else {}
                ),
            },
            revision=pending.revision + 1,
        )
        manager._stored_state = replace(
            manager._stored_state,
            manual_requests=(legacy_cancelled,),
        )

        replanned = await manager.async_plan_automatic(now=now)

    assert request_id not in replanned["created_request_ids"]
    assert manager._request(request_id) == legacy_cancelled

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")):
        repaired = await manager.async_plan_automatic(
            now=now,
            replace_legacy_cancelled=True,
        )

    assert request_id in repaired["created_request_ids"]
    assert manager._request(request_id).status == "pending"


async def test_cancellation_winning_commit_race_is_not_replayed(
    hass: HomeAssistant,
) -> None:
    """Recheck terminal ownership when cancellation commits during planning."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    request_id = f"automatic:{zone.unique_id}:2026-07-27"
    manager._stored_state = replace(
        manager._stored_state,
        automation_enabled=True,
        manual_requests=(),
    )

    with patch.object(dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("UTC")):
        await manager.async_plan_automatic(now=now)
        await manager._command_lock.acquire()
        plan_task = hass.async_create_task(
            manager._async_plan_automatic_locked(dry_run=False, now=now)
        )
        await asyncio.sleep(0)
        pending = manager._request(request_id)
        assert pending is not None
        cancelled = _with_automatic_cancellation_reason(
            replace(pending, status="cancelled", revision=pending.revision + 1),
            AutomaticCancellationReason.USER_REQUESTED,
        )
        manager._stored_state = replace(
            manager._stored_state,
            manual_requests=manager._with_request(cancelled),
        )
        manager._command_lock.release()
        await plan_task

    matching = [
        request for request in manager.list_manual_requests() if request["request_id"] == request_id
    ]
    assert len(matching) == 1
    assert matching[0]["status"] == "cancelled"


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


async def test_home_assistant_stop_persists_clean_dispatcher_shutdown(
    hass: HomeAssistant,
) -> None:
    """Close dispatcher diagnostics when Home Assistant itself stops."""
    entry, _zone = await _setup_v2_installation(hass)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    stopped = (await IrrigationStore(hass, entry.entry_id).async_load()).dispatcher_diagnostic
    assert stopped is not None
    assert stopped.current_reason == "clean_shutdown"
    assert stopped.clean_shutdown is True


async def test_concurrent_shutdown_callers_wait_for_persistence(
    hass: HomeAssistant,
) -> None:
    """Make every shutdown caller await the same durable completion."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    save_started = asyncio.Event()
    allow_save = asyncio.Event()
    original_save = manager._store.async_save

    async def delayed_save(state) -> None:
        save_started.set()
        await allow_save.wait()
        await original_save(state)

    with patch.object(manager._store, "async_save", side_effect=delayed_save):
        first = hass.async_create_task(manager.async_shutdown())
        await save_started.wait()
        second = hass.async_create_task(manager.async_shutdown())
        await asyncio.sleep(0)

        assert not second.done()
        allow_save.set()
        await asyncio.gather(first, second)

    stopped = (await IrrigationStore(hass, entry.entry_id).async_load()).dispatcher_diagnostic
    assert stopped is not None
    assert stopped.current_reason == "clean_shutdown"
    assert stopped.clean_shutdown is True


async def test_failed_shutdown_persistence_can_be_retried(
    hass: HomeAssistant,
) -> None:
    """Retry a clean shutdown after its first durable write fails."""
    entry, _zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    original_save = manager._store.async_save
    attempts = 0

    async def flaky_save(state) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("temporary store failure")
        await original_save(state)

    with patch.object(manager._store, "async_save", side_effect=flaky_save):
        await manager.async_shutdown()

    assert attempts == 2
    stopped = (await IrrigationStore(hass, entry.entry_id).async_load()).dispatcher_diagnostic
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


async def test_due_automatic_order_is_durably_postponed_to_make_up_window(
    hass: HomeAssistant,
) -> None:
    """Persist forecast evidence and keep the original request identity."""
    entry, zone = await _setup_v2_installation(
        hass,
        installation_overrides={
            "weather_module_enabled": True,
            "weather_sources": {"forecast": "weather.home"},
        },
        zone_overrides={
            "base_target": 600.0,
            "use_weather_adjustment": True,
            "watering_mode": "demand",
            "crop_factor": 1.0,
            "effective_rain_factor": 1.0,
            "demand_threshold_mm": 2.0,
            "maximum_deficit_mm": 50.0,
            "effective_application_rate_mm_h": 10.0,
            "use_forecast_postponement": True,
            "maximum_make_up_days": 2,
            "minimum_forecast_precipitation_mm": 3.0,
            "minimum_forecast_probability": 70.0,
            "maximum_make_up_target": 900.0,
            "make_up_schedule": [
                {
                    "weekday": weekday,
                    "start": (
                        "06:00:00"
                        if weekday == "saturday"
                        else "04:00:00"
                        if weekday == "sunday"
                        else None
                    ),
                    "end": (
                        "08:00:00"
                        if weekday == "saturday"
                        else "06:00:00"
                        if weekday == "sunday"
                        else None
                    ),
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
        },
    )
    manager = entry.runtime_data.manager
    manager._installation_data.update(
        {
            "weather_module_enabled": True,
            "weather_sources": {"forecast": "weather.home"},
        }
    )
    manager._zone_configs[0].data.update(
        {
            "use_weather_adjustment": True,
            "use_forecast_postponement": True,
        }
    )
    manager._stored_state = replace(manager._stored_state, manual_requests=())
    manager._zone_configs[0].data["weekly_schedule"] = [
        {
            "weekday": weekday,
            "start": "05:00:00" if weekday == "friday" else None,
            "end": "07:00:00" if weekday == "friday" else None,
            "target": None,
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
    timezone = ZoneInfo("Europe/Zurich")
    due = datetime(2026, 7, 31, 5, tzinfo=timezone).astimezone(UTC)
    forecast = ForecastFetchResult(
        periods=(
            ForecastPeriod(
                starts_at=datetime(2026, 7, 31, 8, tzinfo=UTC),
                ends_at=datetime(2026, 7, 31, 9, tzinfo=UTC),
                precipitation_mm=4.0,
                probability_percent=85.0,
            ),
        ),
        quality="valid",
        warnings=(),
        forecast_type="hourly",
    )
    observations = {
        "forecast": {
            "quality": "available",
            "source_entity_id": "weather.home",
            "supported_forecast_types": ["hourly"],
        }
    }
    high_demand = WaterBalanceTargetResult(
        state=None,
        outcome="execute",
        final_target=2_400.0,
        fallback_strategy="none",
        quality="valid",
        deficit_target=2_400.0,
    )

    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            AsyncMock(return_value=forecast),
        ),
        patch(
            "custom_components.irrigation_manager.manager.update_water_balance",
            return_value=high_demand,
        ),
    ):
        report = await manager.async_plan_automatic(now=due)

    request_id = f"automatic:{zone.unique_id}:2026-07-31"
    assert request_id in report["created_request_ids"]
    request = manager._request(request_id)
    assert request is not None
    assert (
        request.requested_start_at
        == datetime(2026, 8, 1, 6, tzinfo=timezone).astimezone(UTC).isoformat()
    ), request.resolved_inputs
    assert (
        request.automatic_window_end
        == datetime(2026, 8, 1, 8, tzinfo=timezone).astimezone(UTC).isoformat()
    )
    assert (
        request.expires_at == datetime(2026, 8, 2, 7, tzinfo=timezone).astimezone(UTC).isoformat()
    )
    assert request.target_value == 900.0
    evidence = request.resolved_inputs["forecast_postponement"]
    assert evidence["reason"] == "forecast_threshold_reached"
    assert evidence["qualified_precipitation_mm"] == pytest.approx(4.0)
    assert evidence["minimum_precipitation_mm"] == 3.0
    assert evidence["minimum_probability_percent"] == 70.0
    assert evidence["quality"] == "valid"
    assert evidence["postponement_count"] == 1
    assert evidence["original_seasonal_target"] == 600.0
    assert evidence["maximum_make_up_target"] == 900.0
    assert evidence["make_up_target_capped"] is True
    assert evidence["considered_periods"] == [
        {
            "starts_at": "2026-07-31T08:00:00+00:00",
            "ends_at": "2026-07-31T09:00:00+00:00",
            "precipitation_mm": 4.0,
            "probability_percent": 85.0,
        }
    ]
    assert (
        evidence["original_window_end"]
        == datetime(2026, 7, 31, 7, tzinfo=timezone).astimezone(UTC).isoformat()
    )
    stored = await IrrigationStore(hass, entry.entry_id).async_load()
    restored = next(item for item in stored.manual_requests if item.request_id == request_id)
    assert restored.resolved_inputs["forecast_postponement"] == evidence
    diagnostic = manager.diagnostics_state_decisions()["forecast_postponements"][request_id]
    assert diagnostic["reason"] == "forecast_threshold_reached"
    assert "source_entity_id" not in diagnostic

    pre_window_skip = WaterBalanceTargetResult(
        state=None,
        outcome="skip",
        final_target=None,
        fallback_strategy="none",
        quality="valid",
        reason="water_deficit_below_threshold",
    )
    before_catch_up = datetime(2026, 7, 31, 12, tzinfo=timezone).astimezone(UTC)
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.update_water_balance",
            return_value=pre_window_skip,
        ),
    ):
        await manager.async_plan_automatic(now=before_catch_up)

    waiting = manager._request(request_id)
    assert waiting is not None
    assert waiting.status == "pending"
    assert waiting.requested_start_at == request.requested_start_at
    assert waiting.resolved_inputs["forecast_evaluation_required"] is True

    repeated_forecast = replace(
        forecast,
        periods=(
            ForecastPeriod(
                starts_at=datetime(2026, 8, 1, 12, tzinfo=UTC),
                ends_at=datetime(2026, 8, 1, 13, tzinfo=UTC),
                precipitation_mm=4.0,
                probability_percent=85.0,
            ),
        ),
    )
    catch_up_due = datetime(2026, 8, 1, 6, tzinfo=timezone).astimezone(UTC)
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            AsyncMock(return_value=repeated_forecast),
        ),
    ):
        await manager.async_plan_automatic(now=catch_up_due)

    repeated = manager._request(request_id)
    assert repeated is not None
    assert (
        repeated.requested_start_at
        == datetime(2026, 8, 2, 4, tzinfo=timezone).astimezone(UTC).isoformat()
    )
    assert repeated.resolved_inputs["forecast_postponement"]["postponement_count"] == 2

    measured_rain = WaterBalanceTargetResult(
        state=None,
        outcome="skip",
        final_target=None,
        fallback_strategy="none",
        quality="valid",
        reason="water_deficit_below_threshold",
    )
    measured_due = datetime(2026, 8, 2, 4, tzinfo=timezone).astimezone(UTC)
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.update_water_balance",
            return_value=measured_rain,
        ),
    ):
        await manager.async_plan_automatic(now=measured_due)

    completed = manager._request(request_id)
    assert completed is not None
    assert completed.status == "completed"
    assert (
        completed.resolved_inputs["forecast_postponement"]["reason"]
        == "measured_rain_satisfied_need"
    )

    manager._stored_state = replace(manager._stored_state, manual_requests=(restored,))

    manager._zone_configs[0].data.update(
        {
            "base_target": 1_200.0,
            "maximum_make_up_target": 1_500.0,
            "use_forecast_postponement": False,
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
        }
    )
    disabled_fetch = AsyncMock()
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            disabled_fetch,
        ),
    ):
        await manager.async_plan_automatic(now=before_catch_up)

    disabled_waiting = manager._request(request_id)
    assert disabled_waiting is not None
    assert disabled_waiting.status == "pending"
    assert disabled_waiting.resolved_inputs["forecast_evaluation_required"] is True
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            disabled_fetch,
        ),
    ):
        await manager.async_plan_automatic(now=catch_up_due)

    disabled = manager._request(request_id)
    assert disabled is not None
    assert disabled.requested_start_at == catch_up_due.isoformat()
    assert disabled.target_value == 600.0
    assert disabled.resolved_inputs["forecast_evaluation_required"] is False
    assert (
        disabled.resolved_inputs["forecast_postponement"]["reason"]
        == "forecast_disabled_during_deferral"
    )
    assert disabled.resolved_inputs["forecast_postponement"]["considered_periods"] == []
    assert (
        disabled.resolved_inputs["forecast_postponement"]["original_window_end"]
        == evidence["original_window_end"]
    )
    disabled_fetch.assert_not_awaited()

    after_deadline = datetime(2026, 8, 20, 8, tzinfo=timezone).astimezone(UTC)
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
    ):
        expiry_report = await manager.async_plan_automatic(now=after_deadline)
    expired = manager._request(request_id)
    assert expired is not None
    assert expired.status == "expired"
    assert expired.resolved_inputs["forecast_postponement"]["reason"] == "make_up_deadline_expired"
    assert expiry_report["expired_make_up_request_ids"] == [request_id]

    manager._stored_state = replace(manager._stored_state, manual_requests=())
    manager._zone_configs[0].data.update(
        {
            "base_target": 600.0,
            "maximum_make_up_target": 900.0,
            "use_forecast_postponement": True,
            "weekly_schedule": [
                {
                    "weekday": weekday,
                    "start": "05:00:00" if weekday == "friday" else None,
                    "end": "07:00:00" if weekday == "friday" else None,
                    "target": None,
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
    )
    next_due = datetime(2026, 8, 7, 5, tzinfo=timezone).astimezone(UTC)
    below_threshold = ForecastFetchResult(
        periods=(
            ForecastPeriod(
                starts_at=datetime(2026, 8, 7, 8, tzinfo=UTC),
                ends_at=datetime(2026, 8, 7, 9, tzinfo=UTC),
                precipitation_mm=2.0,
                probability_percent=85.0,
            ),
        ),
        quality="valid",
        warnings=(),
        forecast_type="hourly",
    )
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            AsyncMock(return_value=below_threshold),
        ),
    ):
        await manager.async_plan_automatic(now=next_due)

    current = manager._request(f"automatic:{zone.unique_id}:2026-08-07")
    assert current is not None
    assert current.requested_start_at == next_due.isoformat()
    assert current.resolved_inputs["forecast_evaluation_required"] is False
    assert (
        current.resolved_inputs["forecast_postponement"]["reason"]
        == "forecast_threshold_not_reached"
    )

    manager._stored_state = replace(manager._stored_state, manual_requests=())
    partial_due = datetime(2026, 8, 14, 5, tzinfo=timezone).astimezone(UTC)
    partial_forecast = replace(
        forecast,
        quality="partial",
        warnings=("forecast_period_incomplete",),
    )
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            AsyncMock(return_value=partial_forecast),
        ),
    ):
        await manager.async_plan_automatic(now=partial_due)

    partial = manager._request(f"automatic:{zone.unique_id}:2026-08-14")
    assert partial is not None
    assert partial.requested_start_at == partial_due.isoformat()
    assert (
        partial.resolved_inputs["forecast_postponement"]["reason"]
        == "forecast_unavailable_execute_current_window"
    )

    manager._stored_state = replace(manager._stored_state, manual_requests=())
    manager._zone_configs[0].data["make_up_schedule"] = [
        {"weekday": weekday, "start": None, "end": None}
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
    no_opportunity_due = datetime(2026, 8, 21, 5, tzinfo=timezone).astimezone(UTC)
    no_opportunity_fetch = AsyncMock()
    with (
        patch.object(dt_util, "DEFAULT_TIME_ZONE", timezone),
        patch(
            "custom_components.irrigation_manager.manager.observe_weather_sources",
            return_value=observations,
        ),
        patch(
            "custom_components.irrigation_manager.manager.async_fetch_forecast",
            no_opportunity_fetch,
        ),
    ):
        await manager.async_plan_automatic(now=no_opportunity_due)

    no_opportunity = manager._request(f"automatic:{zone.unique_id}:2026-08-21")
    assert no_opportunity is not None
    assert no_opportunity.requested_start_at == no_opportunity_due.isoformat()
    assert (
        no_opportunity.resolved_inputs["forecast_postponement"]["reason"]
        == "no_future_make_up_opportunity"
    )
    no_opportunity_fetch.assert_not_awaited()


def test_due_forecast_preflight_blocks_automatic_actuation_until_replanned() -> None:
    """A persisted evaluation marker is an atomic dispatcher barrier."""
    now = datetime(2026, 7, 31, 3, tzinfo=UTC)
    request = ManualIrrigationRequest(
        request_id="automatic:zone:2026-07-31",
        sequence=1,
        zone_id="zone",
        zone_subentry_id="zone-subentry",
        zone_name="Lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=600,
        remaining_value=600,
        created_at=now.isoformat(),
        requested_start_at=now.isoformat(),
        expires_at=(now + timedelta(hours=2)).isoformat(),
        source="automatic",
        resolved_inputs={"forecast_evaluation_required": True},
    )

    assert IrrigationManager._forecast_preflight_required(request, now=now) is True
    evaluated = replace(
        request,
        resolved_inputs={"forecast_evaluation_required": False},
    )
    assert IrrigationManager._forecast_preflight_required(evaluated, now=now) is False


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
        watering_started_at=(now - timedelta(seconds=20)).isoformat(),
        watering_ended_at=(now - timedelta(seconds=10)).isoformat(),
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
            watering_ended_at=(now - timedelta(seconds=10)).isoformat(),
            request_id=request.request_id,
            execution_id=execution.execution_id,
        ),
    )
    manager._meter.read_liters = AsyncMock(return_value=112)

    await manager._async_recover_interrupted_execution()

    recovered = manager._stored_state.irrigation_executions[-1]
    assert recovered.delivered_liters == 12
    assert recovered.delivered_duration_seconds == pytest.approx(10, abs=1)
    assert recovered.measurement_quality == "measured"
    assert manager._stored_state.installation_total_liters == 12
    assert any(
        event.request_id == request.request_id and event.new_reason == "cancelled"
        for event in manager._stored_state.dispatcher_diagnostic_history
    )


def _partial_boundary_state(
    manager: IrrigationManager,
    zone: ConfigSubentry,
    *,
    now: datetime,
    boundary: str,
    volume_control: bool = False,
) -> StoredInstallationState:
    """Build one internally consistent persisted boundary for restart tests."""
    volume = volume_control or boundary == "volume_watering"
    terminal = boundary == "terminal"
    target_type = "volume" if volume else "duration"
    target_value = 20.0 if volume else 60.0
    portion_target = 10.0 if volume else 60.0
    started = now - timedelta(seconds=30)
    ended = now - timedelta(seconds=5)
    policy = PortionPolicySnapshot(
        target_type=target_type,
        maximum_portion_target=portion_target,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=3_600.0,
    )
    delivered = target_value if terminal else 0.0
    request = ManualIrrigationRequest(
        request_id=f"recover-{boundary}-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type=target_type,
        target_value=target_value,
        remaining_value=0.0 if terminal else target_value,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        operation_deadline_at=(now + timedelta(hours=1)).isoformat(),
        delivery_runtime_limit_seconds=120.0,
        status="completed" if terminal else "executing",
        execution_id=f"recover-{boundary}-execution",
        portion_policy=policy,
    )
    process = IrrigationExecutionState(
        execution_id=f"recover-{boundary}-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type=target_type,
        target_value=target_value,
        remaining_value=0.0 if terminal else target_value,
        status="completed" if terminal else "watering",
        created_at=request.created_at,
        operation_deadline_at=request.operation_deadline_at,
        delivery_runtime_limit_seconds=120.0,
        delivered_liters=delivered if volume else 0.0,
        delivered_duration_seconds=delivered if not volume else 0.0,
        watering_started_at=(
            started.isoformat() if boundary in {"watering", "closed", "terminal"} else None
        ),
        watering_ended_at=ended.isoformat() if boundary in {"closed", "terminal"} else None,
        ended_at=ended.isoformat() if terminal else None,
        result="target_reached" if terminal else None,
        portion_policy=policy,
        process_started_at=request.created_at,
        process_deadline_at=request.operation_deadline_at,
        next_portion_sequence=2,
        completed_portion_count=1 if terminal else 0,
    )
    opening = boundary in {
        "opening",
        "opening_zero",
        "watering",
        "volume_watering",
        "closed",
    }
    watering = boundary in {"watering", "volume_watering", "closed"}
    portion = IrrigationPortionState(
        portion_id=f"recover-{boundary}-execution:1",
        execution_id=process.execution_id,
        sequence=1,
        target_type=target_type,
        target_value=portion_target if not terminal else target_value,
        status="settled" if terminal else "watering" if watering else "prepared",
        prepared_at=request.created_at,
        opening_attempted_at=started.isoformat() if opening or terminal else None,
        watering_started_at=started.isoformat() if watering or terminal else None,
        watering_ended_at=ended.isoformat() if boundary in {"closed", "terminal"} else None,
        delivered_liters=delivered if volume else 0.0,
        delivered_duration_seconds=delivered if not volume else 0.0,
        result="target_reached" if terminal else None,
        measurement_quality="measured" if volume else "unavailable",
    )
    active = ActiveExecutionState(
        zone_id=zone.unique_id,
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=100.0 if volume or boundary == "opening_zero" else None,
        prepared_at=request.created_at,
        watering_started_at=started.isoformat() if watering or terminal else None,
        requested_duration_seconds=120.0 if volume else 60.0,
        watering_ended_at=ended.isoformat() if boundary in {"closed", "terminal"} else None,
        requested_amount_liters=portion_target if volume else None,
        zone_opening_at=started.isoformat() if opening or terminal else None,
        request_id=request.request_id,
        execution_id=process.execution_id,
        portion_id=portion.portion_id,
        portion_sequence=portion.sequence,
    )
    return replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(process,),
        irrigation_portions=(portion,),
        active_execution=active,
    )


async def test_zone_history_keeps_one_execution_and_exposes_portions_as_details(
    hass: HomeAssistant,
) -> None:
    """Read-only history aggregates by execution while retaining subordinate evidence."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        manager,
        zone,
        now=datetime.now(UTC),
        boundary="terminal",
    )
    manager._stored_state = state
    portion = state.irrigation_portions[0]

    page = manager.zone_history_page(
        zone_subentry_id=zone.subentry_id,
        offset=0,
        limit=20,
    )

    assert page["total"] == 1
    assert len(page["items"]) == 1
    item = page["items"][0]
    assert item["portion_count"] == 1
    assert item["portions"] == [
        {
            "portion_id": "recover-terminal-execution:1",
            "sequence": 1,
            "status": "settled",
            "target_type": "duration",
            "target_value": 60.0,
            "started_at": portion.watering_started_at,
            "ended_at": portion.watering_ended_at,
            "actual_duration": 60.0,
            "actual_water": None,
            "result": "target_reached",
        }
    ]


async def _restart_entry_with_state(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    state: StoredInstallationState,
) -> IrrigationManager:
    """Persist one crash boundary and create a fresh manager through HA setup."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await IrrigationStore(hass, entry.entry_id).async_save(state)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data.manager


@pytest.mark.parametrize(
    ("boundary", "expected_process_status", "expected_reason"),
    [
        ("prepared", "watering", "portion_ready"),
        ("opening", "failed", "portion_recovery_unsafe"),
        ("closed", "soaking", "soak_pause"),
        ("terminal", "failed", "portion_state_inconsistent"),
    ],
)
async def test_persisted_time_boundary_is_recovered_by_fresh_manager(
    hass: HomeAssistant,
    boundary: str,
    expected_process_status: str,
    expected_reason: str,
) -> None:
    """Exercise time-control recovery through Store load and a new HA manager instance."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    old_manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        old_manager,
        zone,
        now=datetime.now(UTC),
        boundary=boundary,
    )
    if boundary == "prepared":
        state = replace(state, operation_enabled=False)

    manager = await _restart_entry_with_state(hass, entry, state)

    process = manager._stored_state.irrigation_executions[0]
    assert process.status == expected_process_status
    assert manager.diagnostics_state_decisions()["partial_irrigation"]["reason"] == expected_reason
    if boundary == "closed":
        assert process.delivered_duration_seconds == pytest.approx(25, abs=2)
        assert manager._stored_state.irrigation_portions[0].status == "settled"
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


@pytest.mark.parametrize(
    ("boundary", "meter_value", "expected_process_status", "expected_reason"),
    [
        ("prepared", 100.0, "watering", "portion_ready"),
        ("opening", 112.0, "failed", "portion_recovery_unsafe"),
        ("watering", 112.0, "soaking", "soak_pause"),
        ("closed", 112.0, "soaking", "soak_pause"),
        ("terminal", 120.0, "failed", "portion_state_inconsistent"),
    ],
)
async def test_persisted_volume_boundary_is_recovered_by_fresh_manager(
    hass: HomeAssistant,
    boundary: str,
    meter_value: float,
    expected_process_status: str,
    expected_reason: str,
) -> None:
    """Exercise every volume-control recovery boundary through persisted HA setup."""
    entry, zone = await _setup_v2_installation(
        hass,
        with_meter=True,
    )
    old_manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        old_manager,
        zone,
        now=datetime.now(UTC),
        boundary=boundary,
        volume_control=True,
    )
    if boundary == "prepared":
        state = replace(state, operation_enabled=False)
    hass.states.async_set(
        "sensor.water",
        str(meter_value),
        {"unit_of_measurement": "L", "device_class": "water"},
    )

    manager = await _restart_entry_with_state(hass, entry, state)

    process = manager._stored_state.irrigation_executions[0]
    assert process.status == expected_process_status
    assert manager.diagnostics_state_decisions()["partial_irrigation"]["reason"] == expected_reason
    if boundary in {"watering", "closed"}:
        assert process.delivered_liters == 12.0
        assert process.remaining_value == 8.0
        assert len(manager._stored_state.water_consumption_history) == 1
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_recovers_soaking_process_and_projects_its_safe_resume(
    hass: HomeAssistant,
) -> None:
    """A restart keeps a valid hardware-free soak pause instead of losing the process."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    old_manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=60.0,
        minimum_soak_seconds=300.0,
        maximum_portions=2,
        maximum_lifetime_seconds=3_600.0,
    )
    request = ManualIrrigationRequest(
        request_id="recover-soaking-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=120.0,
        remaining_value=60.0,
        created_at=(now - timedelta(minutes=2)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        operation_deadline_at=(now + timedelta(hours=1)).isoformat(),
        delivery_runtime_limit_seconds=120.0,
        status="executing",
        execution_id="recover-soaking-execution",
        portion_policy=policy,
    )
    process = IrrigationExecutionState(
        execution_id="recover-soaking-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=120.0,
        remaining_value=60.0,
        status="soaking",
        created_at=request.created_at,
        operation_deadline_at=request.operation_deadline_at,
        delivery_runtime_limit_seconds=120.0,
        delivered_duration_seconds=60.0,
        portion_policy=policy,
        process_started_at=request.created_at,
        process_deadline_at=request.operation_deadline_at,
        next_portion_at=(now + timedelta(minutes=5)).isoformat(),
        next_portion_sequence=2,
        completed_portion_count=1,
    )
    portion = IrrigationPortionState(
        portion_id="recover-soaking-execution:1",
        execution_id=process.execution_id,
        sequence=1,
        target_type="duration",
        target_value=60.0,
        status="settled",
        prepared_at=request.created_at,
        watering_started_at=request.created_at,
        watering_ended_at=(now - timedelta(minutes=1)).isoformat(),
        delivered_duration_seconds=60.0,
        result="target_reached",
        measurement_quality="unavailable",
    )
    state = replace(
        old_manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(process,),
        irrigation_portions=(portion,),
    )
    manager = await _restart_entry_with_state(hass, entry, state)

    snapshot = manager.snapshot()
    assert snapshot.status == "soaking"
    assert snapshot.active_request_id == request.request_id
    assert snapshot.active_execution_id == process.execution_id
    assert snapshot.partial_remaining_value == 60.0
    assert snapshot.partial_next_portion_at == process.next_portion_at
    assert snapshot.partial_current_portion == 2
    assert snapshot.partial_maximum_portions == 2
    assert manager._stored_state.active_execution is None
    assert manager.diagnostics_state_decisions()["partial_irrigation"]["reason"] == "soak_pause"
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_recovers_and_projects_multiple_soaking_zones(
    hass: HomeAssistant,
) -> None:
    """Independent hardware-free pauses survive one restart without hiding a zone."""
    entry, lawn = await _setup_v2_installation(
        hass,
    )
    old_manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=60.0,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=3_600.0,
    )

    def soaking_records(
        *,
        suffix: str,
        sequence: int,
        zone_id: str,
        zone_subentry_id: str,
        zone_name: str,
        zone_valve: str,
        resume_minutes: int,
    ) -> tuple[ManualIrrigationRequest, IrrigationExecutionState, IrrigationPortionState]:
        request = ManualIrrigationRequest(
            request_id=f"recover-{suffix}-request",
            sequence=sequence,
            zone_id=zone_id,
            zone_subentry_id=zone_subentry_id,
            zone_name=zone_name,
            zone_valve=zone_valve,
            main_valve=None,
            target_type="duration",
            target_value=120.0,
            remaining_value=60.0,
            created_at=(now - timedelta(minutes=2)).isoformat(),
            expires_at=(now + timedelta(hours=1)).isoformat(),
            operation_deadline_at=(now + timedelta(hours=1)).isoformat(),
            delivery_runtime_limit_seconds=120.0,
            status="executing",
            execution_id=f"recover-{suffix}-execution",
            portion_policy=policy,
        )
        process = IrrigationExecutionState(
            execution_id=request.execution_id or "",
            request_id=request.request_id,
            zone_id=zone_id,
            target_type="duration",
            target_value=120.0,
            remaining_value=60.0,
            status="soaking",
            created_at=request.created_at,
            operation_deadline_at=request.operation_deadline_at,
            delivery_runtime_limit_seconds=120.0,
            delivered_duration_seconds=60.0,
            portion_policy=policy,
            process_started_at=request.created_at,
            process_deadline_at=request.operation_deadline_at,
            next_portion_at=(now + timedelta(minutes=resume_minutes)).isoformat(),
            next_portion_sequence=2,
            completed_portion_count=1,
        )
        portion = IrrigationPortionState(
            portion_id=f"{process.execution_id}:1",
            execution_id=process.execution_id,
            sequence=1,
            target_type="duration",
            target_value=60.0,
            status="settled",
            prepared_at=request.created_at,
            watering_started_at=request.created_at,
            watering_ended_at=(now - timedelta(minutes=1)).isoformat(),
            delivered_duration_seconds=60.0,
            result="target_reached",
            measurement_quality="unavailable",
        )
        return request, process, portion

    beds = ConfigSubentry(
        data=MappingProxyType(
            {
                **dict(lawn.data),
                "name": "Beds",
                "zone_valve": "switch.beds",
            }
        ),
        subentry_id="beds-v2-subentry",
        subentry_type="zone",
        title="Beds",
        unique_id="beds-v2-runtime",
    )
    hass.states.async_set("switch.beds", STATE_OFF)
    lawn_records = soaking_records(
        suffix="lawn",
        sequence=1,
        zone_id=lawn.unique_id,
        zone_subentry_id=lawn.subentry_id,
        zone_name=lawn.title,
        zone_valve="switch.lawn",
        resume_minutes=5,
    )
    beds_records = soaking_records(
        suffix="beds",
        sequence=2,
        zone_id=beds.unique_id,
        zone_subentry_id=beds.subentry_id,
        zone_name=beds.title,
        zone_valve="switch.beds",
        resume_minutes=4,
    )
    state = replace(
        old_manager._stored_state,
        manual_requests=(lawn_records[0], beds_records[0]),
        irrigation_executions=(lawn_records[1], beds_records[1]),
        irrigation_portions=(lawn_records[2], beds_records[2]),
    )

    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.config_entries.async_add_subentry(entry, beds)
    await IrrigationStore(hass, entry.entry_id).async_save(state)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data.manager

    snapshot = manager.snapshot()
    assert snapshot.status == "soaking"
    assert snapshot.installation_safety_lock is None
    assert {process.zone_id for process in snapshot.partial_processes} == {
        lawn.unique_id,
        beds.unique_id,
    }
    assert snapshot.zone_status[lawn.unique_id] == "soaking"
    assert snapshot.zone_status[beds.unique_id] == "soaking"
    decisions = manager.diagnostics_state_decisions()
    assert len(decisions["partial_irrigation_processes"]) == 2
    assert {process["reason"] for process in decisions["partial_irrigation_processes"]} == {
        "soak_pause"
    }
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_settles_reliably_timed_partial_delivery_exactly_once(
    hass: HomeAssistant,
) -> None:
    """Confirmed closure turns an interrupted timed portion into one durable settlement."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    started = now - timedelta(seconds=30)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=60.0,
        minimum_soak_seconds=300.0,
        maximum_portions=3,
        maximum_lifetime_seconds=3_600.0,
    )
    request = ManualIrrigationRequest(
        request_id="recover-watering-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=120.0,
        remaining_value=120.0,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        operation_deadline_at=(now + timedelta(hours=1)).isoformat(),
        delivery_runtime_limit_seconds=120.0,
        status="executing",
        execution_id="recover-watering-execution",
        portion_policy=policy,
    )
    process = IrrigationExecutionState(
        execution_id="recover-watering-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=120.0,
        remaining_value=120.0,
        status="watering",
        created_at=request.created_at,
        operation_deadline_at=request.operation_deadline_at,
        delivery_runtime_limit_seconds=120.0,
        watering_started_at=started.isoformat(),
        portion_policy=policy,
        process_started_at=request.created_at,
        process_deadline_at=request.operation_deadline_at,
        next_portion_sequence=2,
    )
    portion = IrrigationPortionState(
        portion_id="recover-watering-execution:1",
        execution_id=process.execution_id,
        sequence=1,
        target_type="duration",
        target_value=60.0,
        status="watering",
        prepared_at=request.created_at,
        opening_attempted_at=started.isoformat(),
        watering_started_at=started.isoformat(),
    )
    active = ActiveExecutionState(
        zone_id=zone.unique_id,
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=None,
        prepared_at=request.created_at,
        watering_started_at=started.isoformat(),
        requested_duration_seconds=60.0,
        zone_opening_at=started.isoformat(),
        request_id=request.request_id,
        execution_id=process.execution_id,
        portion_id=portion.portion_id,
        portion_sequence=portion.sequence,
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(process,),
        irrigation_portions=(portion,),
        active_execution=active,
    )
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    recovered = manager._stored_state.irrigation_executions[0]
    assert recovered.status == "soaking"
    assert recovered.completed_portion_count == 1
    assert recovered.delivered_duration_seconds == pytest.approx(30, abs=2)
    assert manager._stored_state.irrigation_portions[0].status == "settled"
    assert manager._stored_state.active_execution is None
    assert manager._stored_state.installation_total_liters == 0.0
    assert manager._stored_state.water_consumption_history == ()
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_fails_closed_when_opening_delivery_cannot_be_proven(
    hass: HomeAssistant,
) -> None:
    """An opening attempt without meter or confirmed opening is never retried as zero."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    now = datetime.now(UTC)
    policy = PortionPolicySnapshot(
        target_type="duration",
        maximum_portion_target=60.0,
        minimum_soak_seconds=300.0,
        maximum_portions=1,
        maximum_lifetime_seconds=3_600.0,
    )
    request = ManualIrrigationRequest(
        request_id="recover-opening-request",
        sequence=1,
        zone_id=zone.unique_id,
        zone_subentry_id=zone.subentry_id,
        zone_name=zone.title,
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60.0,
        remaining_value=60.0,
        created_at=(now - timedelta(minutes=1)).isoformat(),
        expires_at=(now + timedelta(hours=1)).isoformat(),
        operation_deadline_at=(now + timedelta(hours=1)).isoformat(),
        delivery_runtime_limit_seconds=60.0,
        status="executing",
        execution_id="recover-opening-execution",
        portion_policy=policy,
    )
    process = IrrigationExecutionState(
        execution_id="recover-opening-execution",
        request_id=request.request_id,
        zone_id=zone.unique_id,
        target_type="duration",
        target_value=60.0,
        remaining_value=60.0,
        status="watering",
        created_at=request.created_at,
        operation_deadline_at=request.operation_deadline_at,
        delivery_runtime_limit_seconds=60.0,
        portion_policy=policy,
        process_started_at=request.created_at,
        process_deadline_at=request.operation_deadline_at,
        next_portion_sequence=2,
    )
    portion = IrrigationPortionState(
        portion_id="recover-opening-execution:1",
        execution_id=process.execution_id,
        sequence=1,
        target_type="duration",
        target_value=60.0,
        status="prepared",
        prepared_at=request.created_at,
        opening_attempted_at=(now - timedelta(seconds=5)).isoformat(),
    )
    active = ActiveExecutionState(
        zone_id=zone.unique_id,
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=None,
        prepared_at=request.created_at,
        watering_started_at=None,
        requested_duration_seconds=60.0,
        zone_opening_at=portion.opening_attempted_at,
        request_id=request.request_id,
        execution_id=process.execution_id,
        portion_id=portion.portion_id,
        portion_sequence=portion.sequence,
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(request,),
        irrigation_executions=(process,),
        irrigation_portions=(portion,),
        active_execution=active,
    )
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    assert manager._stored_state.active_execution is None
    assert manager._stored_state.irrigation_executions[0].status == "failed"
    assert manager._stored_state.irrigation_portions[0].status == "interrupted"
    assert manager.snapshot().installation_safety_lock == "portion_recovery_unsafe"
    assert (
        manager.diagnostics_state_decisions()["partial_irrigation"]["reason"]
        == "portion_recovery_unsafe"
    )
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


@pytest.mark.parametrize("boundary", ["prepared", "opening_zero"])
async def test_initialize_redispatches_only_provably_dry_prepared_portion(
    hass: HomeAssistant,
    boundary: str,
) -> None:
    """Prepared work retains its identity only before opening or after measured zero delivery."""
    entry, zone = await _setup_v2_installation(
        hass,
        with_meter=boundary == "opening_zero",
    )
    manager = entry.runtime_data.manager
    manager._stored_state = replace(
        _partial_boundary_state(
            manager,
            zone,
            now=datetime.now(UTC),
            boundary=boundary,
        ),
        operation_enabled=False,
    )
    original_portion_id = manager._stored_state.irrigation_portions[0].portion_id
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    recovered = manager._stored_state.irrigation_portions[0]
    assert manager._stored_state.active_execution is None
    assert recovered.portion_id == original_portion_id
    assert recovered.status == "prepared"
    assert recovered.opening_attempted_at is None
    assert manager._stored_state.irrigation_executions[0].completed_portion_count == 0
    assert manager.diagnostics_state_decisions()["partial_irrigation"]["reason"] == "portion_ready"
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_fails_closed_when_any_managed_valve_cannot_be_confirmed(
    hass: HomeAssistant,
) -> None:
    """Recovery never evaluates a prepared checkpoint after incomplete valve closure."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    manager._stored_state = _partial_boundary_state(
        manager,
        zone,
        now=datetime.now(UTC),
        boundary="prepared",
    )
    manager._actuators.close = AsyncMock(side_effect=HomeAssistantError("no feedback"))

    await manager.async_initialize()

    assert manager._stored_state.active_execution is None
    assert manager._stored_state.irrigation_executions[0].status == "failed"
    assert manager.snapshot().installation_safety_lock == "portion_recovery_unsafe"
    assert manager._actuators.close.await_count >= 1
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_fails_closed_for_contradictory_partial_timestamps(
    hass: HomeAssistant,
) -> None:
    """A prepared portion with an impossible start timestamp is state corruption, not zero use."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        manager,
        zone,
        now=datetime.now(UTC),
        boundary="prepared",
    )
    assert state.active_execution is not None
    manager._stored_state = replace(
        state,
        active_execution=replace(
            state.active_execution,
            watering_started_at=datetime.now(UTC).isoformat(),
        ),
    )
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    assert manager._stored_state.irrigation_executions[0].status == "failed"
    assert manager.snapshot().installation_safety_lock == "portion_state_inconsistent"
    assert (
        manager.diagnostics_state_decisions()["partial_irrigation"]["reason"]
        == "portion_state_inconsistent"
    )
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_fails_closed_for_mislinked_partial_request(
    hass: HomeAssistant,
) -> None:
    """Recovery rejects a process whose owning request no longer points back to it."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        manager,
        zone,
        now=datetime.now(UTC),
        boundary="prepared",
    )
    request = replace(state.manual_requests[0], execution_id="another-execution")
    manager._stored_state = replace(state, manual_requests=(request,))
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    assert manager._stored_state.irrigation_executions[0].status == "failed"
    assert manager.snapshot().installation_safety_lock == "portion_state_inconsistent"
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_recovers_volume_portion_from_reliable_meter_delta(
    hass: HomeAssistant,
) -> None:
    """A volume process continues only after the cumulative meter proves its delivery."""
    entry, zone = await _setup_v2_installation(
        hass,
        with_meter=True,
    )
    old_manager = entry.runtime_data.manager
    state = _partial_boundary_state(
        old_manager,
        zone,
        now=datetime.now(UTC),
        boundary="volume_watering",
    )
    hass.states.async_set(
        "sensor.water",
        "112",
        {"unit_of_measurement": "L", "device_class": "water"},
    )

    manager = await _restart_entry_with_state(hass, entry, state)

    recovered = manager._stored_state.irrigation_executions[0]
    assert recovered.status == "soaking"
    assert recovered.delivered_liters == 12.0
    assert recovered.remaining_value == 8.0
    assert manager._stored_state.installation_total_liters == 12.0
    assert len(manager._stored_state.water_consumption_history) == 1
    assert manager._stored_state.water_consumption_history[0].portion_id.endswith(":1")
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
    )


async def test_initialize_rejects_terminal_process_with_active_checkpoint(
    hass: HomeAssistant,
) -> None:
    """Contradictory terminal hardware ownership is locked instead of silently cleared."""
    entry, zone = await _setup_v2_installation(
        hass,
    )
    manager = entry.runtime_data.manager
    manager._stored_state = _partial_boundary_state(
        manager,
        zone,
        now=datetime.now(UTC),
        boundary="terminal",
    )
    manager._actuators.close = AsyncMock()

    await manager.async_initialize()

    assert manager._stored_state.active_execution is None
    assert manager._stored_state.irrigation_executions[0].status == "failed"
    assert manager.snapshot().installation_safety_lock == "portion_state_inconsistent"
    assert (
        manager.diagnostics_state_decisions()["partial_irrigation"]["reason"]
        == "portion_state_inconsistent"
    )
    manager._dispatcher_task.cancel()
    manager._automatic_planner_task.cancel()
    await asyncio.gather(
        manager._dispatcher_task,
        manager._automatic_planner_task,
        return_exceptions=True,
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
