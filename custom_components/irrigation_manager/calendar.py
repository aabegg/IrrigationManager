"""Read-only irrigation order calendar platform."""

from datetime import datetime, timedelta
from typing import cast, override

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, INTEGRATION_NAME
from .manager import IrrigationManager
from .runtime import IrrigationConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one read-only calendar for an irrigation installation."""
    async_add_entities(
        [
            IrrigationCalendar(
                manager=entry.runtime_data.manager,
                installation_id=entry.unique_id or entry.entry_id,
                installation_name=entry.title,
            )
        ]
    )


class IrrigationCalendar(CalendarEntity):
    """Expose automatic and explicitly scheduled manual orders without writes."""

    _attr_has_entity_name = True
    _attr_translation_key = "schedule"

    def __init__(
        self, *, manager: IrrigationManager, installation_id: str, installation_name: str
    ) -> None:
        """Initialize an installation-scoped calendar."""
        self._manager = manager
        self._attr_unique_id = f"{installation_id}_calendar"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, installation_id)},
            name=installation_name,
            manufacturer=INTEGRATION_NAME,
        )

    @property
    @override
    def should_poll(self) -> bool:
        """Return false because requests push state through the manager."""
        return False

    @property
    @override
    def event(self) -> CalendarEvent | None:
        """Return the active or next scheduled order."""
        now = dt_util.now()
        events = self._events(now - timedelta(days=1), now + timedelta(days=366))
        return min(
            (event for event in events if event.end_datetime_local > now),
            key=lambda event: event.start_datetime_local,
            default=None,
        )

    @override
    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return all order events overlapping the requested range."""
        return self._events(start_date, end_date)

    def _events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return [
            CalendarEvent(
                start=cast(datetime, record["start"]),
                end=cast(datetime, record["end"]),
                summary=str(record["summary"]),
                description=str(record["description"]),
                uid=str(record["uid"]),
            )
            for record in self._manager.calendar_events(start=start, end=end)
        ]
