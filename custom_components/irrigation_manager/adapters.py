"""Home Assistant adapters for the executor ports."""

import asyncio

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfVolume,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import VolumeConverter

from .meter import CumulativeMeter


class HomeAssistantActuators:
    """Control switch and valve entities through native HA actions."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the actuator adapter."""
        self._hass = hass

    async def open(self, entity_id: str) -> None:
        """Open a switch or valve and wait for the action call."""
        domain = entity_id.partition(".")[0]
        service = "open_valve" if domain == "valve" else "turn_on"
        await self._hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await self._async_wait_for_state(entity_id, {STATE_ON, "open"})

    async def close(self, entity_id: str) -> None:
        """Close a switch or valve and wait for the action call."""
        domain = entity_id.partition(".")[0]
        service = "close_valve" if domain == "valve" else "turn_off"
        await self._hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        await self._async_wait_for_state(entity_id, {STATE_OFF, "closed"})

    async def is_open(self, entity_id: str) -> bool:
        """Read immediate logical feedback after an actuator command."""
        state = self._hass.states.get(entity_id)
        return state is not None and state.state in {STATE_ON, "open"}

    async def _async_wait_for_state(self, entity_id: str, expected_states: set[str]) -> None:
        """Wait briefly for delayed actuator feedback."""
        changed = asyncio.Event()

        @callback
        def state_changed(event: Event[EventStateChangedData]) -> None:
            new_state = event.data["new_state"]
            if new_state is not None and new_state.state in expected_states:
                changed.set()

        unsubscribe = async_track_state_change_event(self._hass, entity_id, state_changed)
        try:
            current = self._hass.states.get(entity_id)
            if current is not None and current.state in expected_states:
                return
            async with asyncio.timeout(5):
                await changed.wait()
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Actuator {entity_id} did not reach the commanded state"
            ) from err
        finally:
            unsubscribe()


class HomeAssistantMeter:
    """Normalize a cumulative HA volume sensor to liters."""

    def __init__(self, hass: HomeAssistant, entity_id: str | None) -> None:
        """Initialize the meter adapter; a missing source reads zero."""
        self._hass = hass
        self._entity_id = entity_id
        self._continuity: CumulativeMeter | None = None

    async def read_liters(self) -> float:
        """Return the cumulative source value converted to liters."""
        if self._entity_id is None:
            return 0.0
        state = self._hass.states.get(self._entity_id)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            raise HomeAssistantError(f"Water meter {self._entity_id} is not available")
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in VolumeConverter.VALID_UNITS:
            raise HomeAssistantError(f"Water meter {self._entity_id} has unsupported unit {unit!r}")
        try:
            value = float(state.state)
        except ValueError as err:
            raise HomeAssistantError(f"Water meter {self._entity_id} is not numeric") from err
        raw_liters = VolumeConverter.convert(value, unit, UnitOfVolume.LITERS)
        self._continuity = (
            CumulativeMeter.start(raw_liters=raw_liters)
            if self._continuity is None
            else self._continuity.update(raw_liters=raw_liters)
        )
        return self._continuity.total_liters


class HomeAssistantClock:
    """Use the event loop's cancellable monotonic sleep."""

    async def sleep(self, seconds: float) -> None:
        """Wait without blocking Home Assistant's event loop."""
        await asyncio.sleep(seconds)

    def monotonic(self) -> float:
        """Return the event loop's monotonic clock."""
        return asyncio.get_running_loop().time()
