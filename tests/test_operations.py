"""Operational events, diagnostics, export, and reconciliation tests."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType

import pytest
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_OFF
from homeassistant.core import Context, Event, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, MockUser

from custom_components.irrigation_manager.const import DOMAIN, EVENT_IRRIGATION_MANAGER
from custom_components.irrigation_manager.diagnostics import async_get_config_entry_diagnostics
from custom_components.irrigation_manager.models import (
    ActiveExecutionState,
    IrrigationExecutionState,
    ManualIrrigationRequest,
    UncreditedBalanceDelivery,
)


async def _setup_installation(hass: HomeAssistant) -> tuple[MockConfigEntry, ConfigSubentry]:
    async def turn_on(call) -> None:
        hass.states.async_set(call.data["entity_id"], "on")

    async def turn_off(call) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    hass.services.async_register("switch", "turn_on", turn_on)
    hass.services.async_register("switch", "turn_off", turn_off)
    hass.states.async_set("switch.lawn", STATE_OFF)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Private garden",
        data={
            "name": "Private garden",
            "weather_entity": "weather.home",
            "operation_enabled": True,
        },
        unique_id="installation-1",
        version=2,
    )
    entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data=MappingProxyType(
            {
                "name": "Back lawn",
                "zone_valve": "switch.lawn",
                "default_duration": 60,
                "area_m2": 10,
                "application_efficiency": 0.5,
                "maximum_deficit_mm": 50,
                "minimum_effective_liters": 0.1,
            }
        ),
        subentry_id="subentry-1",
        subentry_type="zone",
        title="Back lawn",
        unique_id="zone-1",
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, subentry


async def test_manual_execution_emits_complete_secret_free_lifecycle(
    hass: HomeAssistant,
) -> None:
    """Publish request, execution, and dose lifecycle events with a stable envelope."""
    entry, subentry = await _setup_installation(hass)
    events: list[Event] = []
    hass.bus.async_listen(EVENT_IRRIGATION_MANAGER, events.append)

    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "duration": 0.001,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    by_type = {event.data["event_type"]: event.data for event in events}
    assert {
        "request_created",
        "execution_started",
        "dose_started",
        "dose_ended",
        "execution_ended",
    } <= by_type.keys()
    for event in events:
        assert set(event.data) == {
            "event_type",
            "installation_id",
            "reason",
            "target",
            "measurements",
            "quality",
            "context",
        }
        assert "switch.lawn" not in str(event.data)
        assert "Private garden" not in str(event.data)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_events_exports_diagnostics_and_reconciliation(hass: HomeAssistant) -> None:
    """Expose bounded portable data and auditable state changes without sensitive values."""
    entry, _ = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    events: list[Event] = []
    hass.bus.async_listen(EVENT_IRRIGATION_MANAGER, events.append)
    execution = IrrigationExecutionState(
        execution_id="execution-1",
        request_id="request-1",
        zone_id="zone-1",
        target_type="volume",
        target_value=20,
        remaining_value=0,
        status="completed",
        created_at="2026-07-21T10:00:00+00:00",
        ended_at="2026-07-21T10:01:00+00:00",
        result="target_reached",
        delivered_liters=20,
        delivered_duration_seconds=60,
    )
    reconciliation = UncreditedBalanceDelivery(
        reconciliation_id="reconciliation-1",
        zone_id="zone-1",
        delivered_liters=20,
        delivered_at="2026-07-21T10:01:00+00:00",
        reason="missing_immutable_balance_snapshot",
        request_id="request-1",
        execution_id="execution-1",
    )
    manager._stored_state = replace(
        manager._stored_state,
        irrigation_executions=(execution,),
        zone_deficit_mm={"zone-1": 10},
        uncredited_balance_deliveries=(reconciliation,),
    )

    portable = await hass.services.async_call(
        DOMAIN,
        "export_config",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert portable["schema_version"] == 1
    assert portable["profile_catalog_version"] == 1
    assert portable["zones"][0]["id"] == "zone-1"
    history = await hass.services.async_call(
        DOMAIN,
        "export_history",
        {"config_entry_id": entry.entry_id, "format": "csv", "limit": 1},
        blocking=True,
        return_response=True,
    )
    assert history["count"] == 1
    assert "execution-1" in history["data"]

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["entry"]["data"]["name"] != "Private garden"
    assert diagnostics["zones"][0]["data"]["zone_valve"] != "switch.lawn"
    assert diagnostics["state_decisions"]["uncredited_balance_count"] == 1
    assert diagnostics["profile_catalog"]["version"] == 1
    assert diagnostics["profile_catalog"]["built_in"]

    response = await hass.services.async_call(
        DOMAIN,
        "resolve_balance_reconciliation",
        {
            "config_entry_id": entry.entry_id,
            "reconciliation_id": reconciliation.reconciliation_id,
            "resolution": "apply",
        },
        blocking=True,
        return_response=True,
    )
    assert response["zone_deficit_mm"] == 9
    assert manager.list_uncredited_balance_deliveries() == []
    event = events[-1].data
    assert event["event_type"] == "balance_correction"
    assert event["target"] == {"type": "zone", "id": "zone-1"}
    assert "switch.lawn" not in str(event)
    assert "Private garden" not in str(event)

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_card_presentation_services_return_open_queue_and_zone_history(
    hass: HomeAssistant,
) -> None:
    """Expose bounded card DTOs without leaking closed orders or another zone's history."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    requests = (
        ManualIrrigationRequest(
            request_id="open-1",
            sequence=1,
            zone_id="zone-1",
            zone_subentry_id=subentry.subentry_id,
            zone_name="Back lawn",
            zone_valve="switch.lawn",
            main_valve=None,
            target_type="duration",
            target_value=60,
            remaining_value=60,
            created_at="2026-07-25T05:00:00+00:00",
            requested_start_at="2026-07-25T05:00:00+00:00",
            expires_at="2026-07-25T07:00:00+00:00",
            source="automatic",
        ),
        ManualIrrigationRequest(
            request_id="closed-1",
            sequence=2,
            zone_id="zone-1",
            zone_subentry_id=subentry.subentry_id,
            zone_name="Back lawn",
            zone_valve="switch.lawn",
            main_valve=None,
            target_type="duration",
            target_value=30,
            remaining_value=0,
            created_at="2026-07-23T05:00:00+00:00",
            expires_at="2026-07-23T07:00:00+00:00",
            status="completed",
        ),
    )
    executions = (
        IrrigationExecutionState(
            execution_id="execution-zone-1",
            request_id="closed-1",
            zone_id="zone-1",
            target_type="duration",
            target_value=30,
            remaining_value=0,
            status="completed",
            created_at="2026-07-23T05:00:00+00:00",
            ended_at="2026-07-23T05:00:30+00:00",
            result="target_reached",
            delivered_duration_seconds=30,
            delivered_liters=0,
        ),
        IrrigationExecutionState(
            execution_id="execution-other-zone",
            request_id="other-1",
            zone_id="zone-2",
            target_type="duration",
            target_value=10,
            remaining_value=0,
            status="completed",
            created_at="2026-07-22T05:00:00+00:00",
            ended_at="2026-07-22T05:00:10+00:00",
            result="target_reached",
            delivered_duration_seconds=10,
        ),
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=requests,
        irrigation_executions=executions,
    )

    orders = await hass.services.async_call(
        DOMAIN,
        "list_card_orders",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        return_response=True,
    )
    assert orders == {
        "orders": [
            {
                "request_id": "open-1",
                "zone_subentry_id": "subentry-1",
                "zone": "Back lawn",
                "source": "automatic",
                "target_type": "duration",
                "target_value": 60,
                "expected_start": "2026-07-25T05:00:00+00:00",
                "status": "pending",
            }
        ]
    }

    history = await hass.services.async_call(
        DOMAIN,
        "list_zone_history",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "offset": 0,
            "limit": 20,
        },
        blocking=True,
        return_response=True,
    )
    assert history["total"] == 1
    assert history["has_more"] is False
    assert history["items"] == [
        {
            "execution_id": "execution-zone-1",
            "started_at": "2026-07-23T05:00:00+00:00",
            "ended_at": "2026-07-23T05:00:30+00:00",
            "source": "manual",
            "target_type": "duration",
            "target_value": 30,
            "result": "completed",
            "actual_duration": 30,
            "actual_water": None,
            "completion_reason": "target_reached",
        }
    ]

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_card_open_orders_matches_dispatcher_priority_and_excludes_started_work(
    hass: HomeAssistant,
) -> None:
    """Show only pending work, with ready manual work ahead of ready automatic work."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 25, 5, tzinfo=UTC)
    common = {
        "zone_id": "zone-1",
        "zone_subentry_id": subentry.subentry_id,
        "zone_name": "Back lawn",
        "zone_valve": "switch.lawn",
        "main_valve": None,
        "target_type": "duration",
        "expires_at": (now + timedelta(hours=2)).isoformat(),
    }
    automatic = ManualIrrigationRequest(
        request_id="automatic-ready",
        sequence=1,
        target_value=60,
        remaining_value=60,
        created_at=(now - timedelta(hours=1)).isoformat(),
        requested_start_at=(now - timedelta(minutes=30)).isoformat(),
        source="automatic",
        **common,
    )
    manual = ManualIrrigationRequest(
        request_id="manual-ready",
        sequence=2,
        target_value=30,
        remaining_value=30,
        created_at=(now - timedelta(minutes=5)).isoformat(),
        **common,
    )
    executing = replace(
        manual,
        request_id="already-started",
        sequence=3,
        status="executing",
        execution_id="execution-1",
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(automatic, manual, executing),
    )

    orders = manager.card_open_orders(now=now)

    assert [order["request_id"] for order in orders] == ["manual-ready", "automatic-ready"]
    assert [order["expected_start"] for order in orders] == [
        "2026-07-25T05:00:00+00:00",
        "2026-07-25T05:00:30+00:00",
    ]
    assert all(order["status"] == "pending" for order in orders)


async def test_card_open_orders_starts_pending_work_after_active_bounded_runtime(
    hass: HomeAssistant,
) -> None:
    """Place only pending orders after the literal remaining active delivery bound."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    now = datetime(2026, 7, 25, 5, 0, 30, tzinfo=UTC)
    pending = ManualIrrigationRequest(
        request_id="pending-after-active",
        sequence=2,
        zone_id="zone-1",
        zone_subentry_id=subentry.subentry_id,
        zone_name="Back lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=60,
        remaining_value=60,
        created_at="2026-07-25T04:00:00+00:00",
        expires_at="2026-07-25T08:00:00+00:00",
    )
    active_request = replace(
        pending,
        request_id="active",
        sequence=1,
        target_value=120,
        remaining_value=120,
        status="executing",
        execution_id="active-execution",
    )
    active = ActiveExecutionState(
        zone_id="zone-1",
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=None,
        prepared_at="2026-07-25T05:00:00+00:00",
        watering_started_at="2026-07-25T05:00:00+00:00",
        requested_duration_seconds=120,
        estimated_flow_l_min=None,
        request_id="active",
        execution_id="active-execution",
        hard_time_limit_seconds=120,
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(active_request, pending),
        active_execution=active,
    )

    orders = manager.card_open_orders(now=now)

    assert [order["request_id"] for order in orders] == ["pending-after-active"]
    assert orders[0]["expected_start"] == "2026-07-25T05:02:00+00:00"


async def test_card_manual_start_resolves_active_execution_in_one_service_call(
    hass: HomeAssistant,
) -> None:
    """Accept a priority-next manual order atomically while another execution is active."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    active_request = ManualIrrigationRequest(
        request_id="active-1",
        sequence=1,
        zone_id="zone-1",
        zone_subentry_id=subentry.subentry_id,
        zone_name="Back lawn",
        zone_valve="switch.lawn",
        main_valve=None,
        target_type="duration",
        target_value=120,
        remaining_value=120,
        created_at="2026-07-24T05:00:00+00:00",
        expires_at="2026-07-25T05:00:00+00:00",
        status="executing",
        execution_id="execution-active",
    )
    active = ActiveExecutionState(
        zone_id="zone-1",
        zone_valve="switch.lawn",
        main_valve=None,
        meter_raw_baseline_liters=None,
        prepared_at="2026-07-24T05:00:00+00:00",
        watering_started_at="2026-07-24T05:00:00+00:00",
        requested_duration_seconds=120,
        estimated_flow_l_min=None,
        request_id="active-1",
        execution_id="execution-active",
    )
    manager._stored_state = replace(
        manager._stored_state,
        manual_requests=(active_request,),
        active_execution=active,
        next_request_sequence=2,
    )

    response = await hass.services.async_call(
        DOMAIN,
        "start_manual_from_card",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "duration": 30,
            "conflict_policy": "priority_next",
        },
        blocking=True,
        return_response=True,
    )

    queued = manager._request(response["request_id"])
    assert queued is not None
    assert queued.status == "pending"
    assert manager._stored_state.active_execution == active

    manager._stored_state = replace(manager._stored_state, active_execution=None)
    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_unmetered_v2_cards_use_status_anchor_and_runtime_roles(
    hass: HomeAssistant,
) -> None:
    """Keep zone cards selectable and useful when no water measurement is configured."""
    entry, _ = await _setup_installation(hass)
    registry = er.async_get(hass)
    anchor_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_zone_status")
    water_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_water_total")
    runtime_id = registry.async_get_entity_id("sensor", DOMAIN, "zone-1_runtime_today")

    assert anchor_id is not None
    assert water_id is None
    assert runtime_id is not None
    anchor = hass.states.get(anchor_id)
    assert anchor.attributes["card_entities"]["anchor"] == anchor_id
    assert "water_today" not in anchor.attributes["card_entities"]
    assert anchor.attributes["card_entities"]["runtime_today"] == runtime_id
    assert anchor.attributes["volume_control_available"] is False

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_portable_import_requires_preview_mapping_confirmation_and_hash(
    hass: HomeAssistant,
) -> None:
    """Never silently import entities or overwrite an existing installation."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    hass.states.async_set("weather.home", "sunny")
    payload = manager.export_portable_config()
    payload["installation"]["config"]["name"] = "Imported garden"
    hass.states.async_set("weather.imported", "sunny")

    preview = await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={"weather.home": "weather.imported"},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=True,
        confirm_overwrite=False,
        expected_config_hash=None,
    )

    assert preview["dry_run"] is True
    assert preview["installation_changed"] is True
    assert entry.title == "Private garden"
    with pytest.raises(HomeAssistantError, match="confirmation"):
        await manager.async_import_portable_config(
            payload=payload,
            entity_remapping={"weather.home": "weather.imported"},
            zone_remapping={"zone-1": subentry.subentry_id},
            dry_run=False,
            confirm_overwrite=False,
            confirm_researched_profiles=True,
            expected_config_hash=preview["config_hash"],
        )

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_portable_import_does_not_trust_researched_profile_confirmation(
    hass: HomeAssistant,
) -> None:
    """Require a new local confirmation even when the export claims it was confirmed."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    hass.states.async_set("weather.home", "sunny")
    payload = manager.export_portable_config()
    payload["installation"]["config"].update(
        {"automation_enabled": True, "hardware_shutoff_acknowledged": True}
    )
    payload["zones"][0]["config"]["automation_enabled"] = True
    payload["zones"][0]["config"].update(
        {
            "plant_profile": "builtin:plant:cool-season-turf:v1",
            "soil_profile": "builtin:soil:sandy-loam:v1",
            "agronomic_values_confirmed": True,
        }
    )
    preview = await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=True,
        confirm_overwrite=False,
        expected_config_hash=None,
    )

    assert preview["profile_confirmation_required"] is True
    assert preview["researched_profile_zones"] == ["zone-1"]
    with pytest.raises(HomeAssistantError, match="local confirmation"):
        await manager.async_import_portable_config(
            payload=payload,
            entity_remapping={},
            zone_remapping={"zone-1": subentry.subentry_id},
            dry_run=False,
            confirm_overwrite=True,
            expected_config_hash=preview["config_hash"],
        )

    await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=False,
        confirm_overwrite=True,
        confirm_researched_profiles=True,
        expected_config_hash=preview["config_hash"],
    )
    assert entry.subentries[subentry.subentry_id].data["agronomic_values_confirmed"] is True
    assert entry.data["hardware_shutoff_acknowledged"] is False
    assert entry.data["automation_enabled"] is False
    assert entry.subentries[subentry.subentry_id].data["automation_enabled"] is False

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_portable_import_does_not_trust_generic_agronomic_confirmation(
    hass: HomeAssistant,
) -> None:
    """Reset an exported confirmation even when no researched profile is referenced."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    payload = manager.export_portable_config()
    payload["zones"][0]["config"]["agronomic_values_confirmed"] = True

    preview = await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=True,
        confirm_overwrite=False,
        expected_config_hash=None,
    )

    assert preview["profile_confirmation_required"] is True
    assert preview["profile_confirmation_zones"] == ["zone-1"]
    assert preview["researched_profile_zones"] == []

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_import_config_service_requires_admin_user(hass: HomeAssistant) -> None:
    """Reject configuration imports from non-admin service-call contexts."""
    entry, subentry = await _setup_installation(hass)
    user = MockUser().add_to_hass(hass)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "import_config",
            {
                "config_entry_id": entry.entry_id,
                "payload": entry.runtime_data.manager.export_portable_config(),
                "zone_remapping": {"zone-1": subentry.subentry_id},
            },
            blocking=True,
            return_response=True,
            context=Context(user_id=user.id),
        )

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        ("archive_zone", {"zone_subentry_id": "subentry-1"}),
        ("restore_zone", {"zone_subentry_id": "subentry-1"}),
        ("suspend_automatic", {"until": datetime.now(UTC) + timedelta(hours=1)}),
        ("resume_automatic", {}),
        ("complete_maintenance_task", {"task_id": "filter"}),
        (
            "snooze_maintenance_task",
            {"task_id": "filter", "until": date.today() + timedelta(days=1)},
        ),
        (
            "update_spring_checklist",
            {"item_id": "valves", "completed": True},
        ),
        ("set_winter_lock", {}),
        ("clear_winter_lock", {}),
        ("reset_emergency_stop", {}),
        ("reset_installation_safety", {}),
        (
            "start_maintenance_test",
            {
                "zone_subentry_id": "subentry-1",
                "duration": 1,
                "kind": "spring_recommission",
            },
        ),
        ("confirm_maintenance_test", {"test_id": "test-1"}),
        ("stop_maintenance_test", {}),
    ],
)
async def test_lifecycle_mutations_require_admin(
    hass: HomeAssistant, service: str, data: dict[str, object]
) -> None:
    """Reject every configuration and lifecycle mutation from a non-admin user."""
    entry, _ = await _setup_installation(hass)
    user = MockUser().add_to_hass(hass)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            service,
            {"config_entry_id": entry.entry_id, **data},
            blocking=True,
            context=Context(user_id=user.id),
        )


async def test_admin_can_suspend_and_resume_automatic_irrigation(
    hass: HomeAssistant,
) -> None:
    """Allow lifecycle controls for an authenticated administrator."""
    entry, _ = await _setup_installation(hass)
    user = MockUser(is_owner=True).add_to_hass(hass)
    context = Context(user_id=user.id)

    await hass.services.async_call(
        DOMAIN,
        "suspend_automatic",
        {
            "config_entry_id": entry.entry_id,
            "until": datetime.now(UTC) + timedelta(hours=1),
        },
        blocking=True,
        context=context,
    )
    await hass.services.async_call(
        DOMAIN,
        "resume_automatic",
        {"config_entry_id": entry.entry_id},
        blocking=True,
        context=context,
    )
    assert entry.runtime_data.manager._stored_state.automatic_suspended_until is None


async def test_manual_irrigation_requires_control_permission_for_its_valve(
    hass: HomeAssistant,
) -> None:
    """Use normal entity permissions for runtime watering without requiring admin."""
    entry, subentry = await _setup_installation(hass)
    denied = MockUser().add_to_hass(hass)

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "start_manual",
            {
                "config_entry_id": entry.entry_id,
                "zone_subentry_id": subentry.subentry_id,
                "duration": 0.001,
            },
            blocking=True,
            context=Context(user_id=denied.id),
        )

    allowed = MockUser().add_to_hass(hass)
    allowed.mock_policy({"entities": True})
    await hass.services.async_call(
        DOMAIN,
        "start_manual",
        {
            "config_entry_id": entry.entry_id,
            "zone_subentry_id": subentry.subentry_id,
            "duration": 0.001,
        },
        blocking=True,
        context=Context(user_id=allowed.id),
    )


async def test_generic_stop_cannot_bypass_maintenance_admin_requirement(
    hass: HomeAssistant,
) -> None:
    """Keep supervised-test lifecycle protection on the generic stop path."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    user = MockUser().add_to_hass(hass)
    await manager.async_start_maintenance_test(
        zone_subentry_id=subentry.subentry_id,
        duration_seconds=1,
    )

    with pytest.raises(Unauthorized):
        await hass.services.async_call(
            DOMAIN,
            "stop",
            {"config_entry_id": entry.entry_id},
            blocking=True,
            context=Context(user_id=user.id),
        )

    assert manager.maintenance_test_active is True
    await manager.async_stop_maintenance_test()


async def test_import_hash_covers_source_and_current_target_zone(hass: HomeAssistant) -> None:
    """Reject a preview after either imported source or mapped target zone changes."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    hass.states.async_set("weather.imported", "sunny")
    payload = manager.export_portable_config()
    preview = await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={"weather.home": "weather.imported"},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=True,
        confirm_overwrite=False,
        expected_config_hash=None,
    )
    hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data={**subentry.data, "default_duration": 120},
    )

    with pytest.raises(HomeAssistantError, match="changed after preview"):
        await manager.async_import_portable_config(
            payload=payload,
            entity_remapping={"weather.home": "weather.imported"},
            zone_remapping={"zone-1": subentry.subentry_id},
            dry_run=False,
            confirm_overwrite=True,
            confirm_researched_profiles=True,
            expected_config_hash=preview["config_hash"],
        )

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_import_rejects_duplicate_targets_and_invalid_remapped_target(
    hass: HomeAssistant,
) -> None:
    """Validate resolved targets before making any config-entry write."""
    entry, subentry = await _setup_installation(hass)
    manager = entry.runtime_data.manager
    payload = manager.export_portable_config()
    second_zone = {**payload["zones"][0], "id": "zone-2"}
    payload["zones"].append(second_zone)

    with pytest.raises(HomeAssistantError, match="same target"):
        await manager.async_import_portable_config(
            payload=payload,
            entity_remapping={"weather.home": "sensor.wrong_domain"},
            zone_remapping={
                "zone-1": subentry.subentry_id,
                "zone-2": subentry.subentry_id,
            },
            dry_run=True,
            confirm_overwrite=False,
            expected_config_hash=None,
        )

    payload["zones"].pop()
    hass.states.async_set("sensor.wrong_domain", "1")
    preview = await manager.async_import_portable_config(
        payload=payload,
        entity_remapping={"weather.home": "sensor.wrong_domain"},
        zone_remapping={"zone-1": subentry.subentry_id},
        dry_run=True,
        confirm_overwrite=False,
        expected_config_hash=None,
    )
    assert preview["entity_issues"] == [
        {
            "entity_id": "sensor.wrong_domain",
            "field": "weather_entity",
            "reason": "wrong_domain",
        }
    ]
    assert entry.title == "Private garden"

    assert await hass.config_entries.async_unload(entry.entry_id)
