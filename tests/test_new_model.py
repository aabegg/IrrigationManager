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
from custom_components.irrigation_manager.models import (
    IrrigationExecutionState,
    ManualIrrigationRequest,
)
from custom_components.irrigation_manager.storage import IrrigationStore


async def _setup_v2_installation(
    hass: HomeAssistant,
    *,
    with_meter: bool = False,
    installation_overrides: dict[str, object] | None = None,
    zone_overrides: dict[str, object] | None = None,
) -> tuple[MockConfigEntry, ConfigSubentry]:
    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], "on")

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
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
        assert result["step_id"] == "installation_zone"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Lawn", "zone_valve": "switch.lawn"}
        )
        assert result["step_id"] == "installation_schedule"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "monday_start": "22:00:00",
                "monday_end": "00:30:00",
                "monday_target": 1800,
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
    }
    zone = next(iter(entry.subentries.values()))
    assert zone.unique_id == "zone-v2"
    assert zone.data["control_type"] == "time"
    assert zone.data["operation_enabled"] is True
    assert zone.data["automation_enabled"] is True
    assert len(zone.data["weekly_schedule"]) == 7
    assert zone.data["weekly_schedule"][0] == {
        "weekday": "monday",
        "start": "22:00:00",
        "end": "00:30:00",
        "target": 1800.0,
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

    assert result["menu_options"] == ["create", "import"]


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
        {"name": "Lawn", "zone_valve": "switch.lawn"},
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], payload)

    partial = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"monday_start": "04:00:00", "monday_target": 600}
    )
    assert partial["step_id"] == "installation_schedule"
    assert partial["errors"] == {"base": "schedule_row_incomplete"}

    overlap = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "monday_start": "23:00:00",
            "monday_end": "02:00:00",
            "monday_target": 1800,
            "tuesday_start": "01:00:00",
            "tuesday_end": "03:00:00",
            "tuesday_target": 600,
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
    assert entry.minor_version == 0
    assert entry.data == {
        "name": "Legacy garden",
        "main_valve": "switch.main",
        "meter_type": "pulse",
        "meter_entity": "sensor.pulses",
        "liters_per_pulse": 2.5,
        "operation_enabled": False,
        "automation_enabled": False,
        "needs_reconfiguration": True,
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
    }


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
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            {
                "wednesday_start": "06:00:00",
                "wednesday_end": "07:00:00",
                "wednesday_target": 300,
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


async def test_weekly_replan_excludes_archived_and_suspended_zones(
    hass: HomeAssistant,
) -> None:
    """Apply durable operational exclusions before creating weekly requests."""
    entry, zone = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 26, 12, tzinfo=UTC)
    zone_id = zone.unique_id
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(),
        archived_zones={zone_id: now.isoformat()},
    )

    archived = await manager.async_plan_automatic(dry_run=True, now=now)
    assert archived["would_create_request_ids"] == []

    manager._stored_state = replace(
        manager._stored_state,
        archived_zones={},
        zone_automatic_suspended_until={zone_id: (now + timedelta(days=15)).isoformat()},
    )
    suspended = await manager.async_plan_automatic(dry_run=True, now=now)
    assert suspended["would_create_request_ids"] == []


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
        await manager.async_start_maintenance_test(
            zone_subentry_id=zone.subentry_id,
            duration_seconds=1,
            kind="calibration",
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
    manager._dispatcher_task = hass.async_create_task(manager._async_dispatch_requests())
    manager._queue_event.set()
    await asyncio.sleep(0.01)

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
        result["flow_id"], {"next_step_id": "v2_installation"}
    )
    assert "automation_enabled" not in {str(key) for key in result["data_schema"].schema}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Garden", "meter_type": "none"}
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
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {"monday_start": "06:00:00", "monday_end": "07:00:00", "monday_target": 300},
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
    assert manager.snapshot().zone_safety_locks == {}


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
        doses=(
            {
                "ended_at": ended_at,
                "duration_seconds": duration,
            },
        ),
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
        result["flow_id"], {"next_step_id": "v2_installation"}
    )
    assert result["step_id"] == "v2_installation"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Garden", "meter_type": "none"}
    )

    assert result["step_id"] == "v2_installation"
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
    assert options["menu_options"] == ["v2_installation", "actions"]
    options = await hass.config_entries.options.async_configure(
        options["flow_id"], {"next_step_id": "v2_installation"}
    )
    installation_fields = {str(key) for key in options["data_schema"].schema}
    assert {"operation_enabled", "automation_enabled"}.isdisjoint(installation_fields)
    options = await hass.config_entries.options.async_configure(
        options["flow_id"],
        {
            "name": "Migrated garden",
            "meter_type": "none",
        },
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
    invalid = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"monday_start": "04:00:00", "monday_target": 600}
    )
    assert invalid["errors"] == {"base": "schedule_row_incomplete"}
    assert entry.subentries[zone.subentry_id].data["needs_reconfiguration"] is True
    completed = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "monday_start": "04:00:00",
            "monday_end": "05:00:00",
            "monday_target": 600,
        },
    )
    assert completed["type"] is FlowResultType.ABORT
    assert "needs_reconfiguration" not in entry.subentries[zone.subentry_id].data


async def test_v2_settings_actions_control_releases_emergency_reset_and_replan(
    hass: HomeAssistant,
) -> None:
    """Expose operational controls with immediate Not-Aus and confirmed reset."""
    entry, _ = await _setup_v2_installation(hass)
    manager = entry.runtime_data.manager

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "actions"}
    )
    assert result["menu_options"] == [
        "installation_releases",
        "emergency_stop",
        "reset_safety",
        "replan",
    ]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "installation_releases"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"operation_enabled": False, "automation_enabled": False}
    )
    assert '"operation_enabled": false' in result["description_placeholders"]["result"]
    assert manager.snapshot().operation_enabled is False

    await manager.async_set_installation_operation(enabled=True)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "actions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "emergency_stop"}
    )
    assert manager.snapshot().emergency_stop is True
    assert result["step_id"] == "action_result"

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "actions"}
    )
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
        result["flow_id"], {"next_step_id": "actions"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "replan"}
    )
    assert '"horizon_days": 14' in result["description_placeholders"]["result"]


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
                result["flow_id"], {"next_step_id": "actions"}
            )
            result = await hass.config_entries.options.async_configure(
                result["flow_id"], {"next_step_id": "installation_releases"}
            )
            configure = hass.config_entries.options.async_configure
            expected_step = "installation_automation_disable"
        else:
            result = await hass.config_entries.subentries.async_init(
                (entry.entry_id, "zone"),
                context={"source": "reconfigure", "subentry_id": zone.subentry_id},
            )
            result = await hass.config_entries.subentries.async_configure(
                result["flow_id"], {"next_step_id": "releases"}
            )
            configure = hass.config_entries.subentries.async_configure
            expected_step = "automation_disable"
        result = await configure(
            result["flow_id"], {"operation_enabled": True, "automation_enabled": False}
        )
        assert result["step_id"] == expected_step
        result = await configure(result["flow_id"], {"active_execution": choice})

    if scope == "installation":
        assert result["step_id"] == "action_result"
        update.assert_awaited_once_with(enabled=False, stop_active=expected_stop)
    else:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "releases_updated"
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
            result["flow_id"], {"next_step_id": "actions"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"next_step_id": "installation_releases"}
        )
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"operation_enabled": True, "automation_enabled": False}
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
            result["flow_id"], {"operation_enabled": True, "automation_enabled": False}
        )
        assert result["type"] is FlowResultType.ABORT

    assert result.get("step_id") not in {
        "installation_automation_disable",
        "automation_disable",
    }
