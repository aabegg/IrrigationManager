"""Read-only irrigation calendar platform tests."""

from datetime import UTC, datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.irrigation_manager.const import DOMAIN

from .test_manual_requests import _setup_installation


async def test_calendar_exposes_stable_future_plan_ranges_without_write_features(
    hass: HomeAssistant,
) -> None:
    """Publish scheduled manual orders with stable UIDs and non-overlapping ranges."""
    entry, zones, _ = await _setup_installation(
        hass,
        zone_specs=(
            ("Lawn", "switch.lawn", 10, 5),
            ("Beds", "switch.beds", 60, 0),
        ),
    )
    start = datetime.now(UTC) + timedelta(hours=1)
    plan = await entry.runtime_data.manager.async_create_manual_plan(
        items=(
            {"zone_subentry_id": zones[0].subentry_id, "duration": 20},
            {"zone_subentry_id": zones[1].subentry_id, "duration": 30},
        ),
        requested_start_at=start,
        expiry_seconds=3600,
    )
    registry = er.async_get(hass)
    calendar_entity_id = registry.async_get_entity_id(
        "calendar", DOMAIN, "installation-requests_calendar"
    )
    assert calendar_entity_id is not None

    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            "entity_id": calendar_entity_id,
            "start_date_time": start - timedelta(minutes=1),
            "end_date_time": start + timedelta(hours=1),
        },
        blocking=True,
        return_response=True,
    )
    events = response[calendar_entity_id]["events"]

    records = entry.runtime_data.manager.calendar_events(
        start=start - timedelta(minutes=1), end=start + timedelta(hours=1)
    )
    assert [record["uid"] for record in records] == plan["request_ids"]
    assert [event["summary"] for event in events] == ["Lawn", "Beds"]
    assert datetime.fromisoformat(events[0]["end"]) <= datetime.fromisoformat(events[1]["start"])
    assert not hass.services.has_service(DOMAIN, "calendar_create_event")
