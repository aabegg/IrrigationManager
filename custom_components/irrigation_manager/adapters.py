"""Home Assistant adapters for the executor ports."""

import asyncio
import math
from datetime import UTC, datetime

from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import VolumeConverter, VolumeFlowRateConverter

from .meter import CumulativeMeter, ImplausibleMeterRegressionError


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

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str | None,
        max_age_seconds: float | None = None,
    ) -> None:
        """Initialize the meter adapter; a missing source reads zero."""
        self._hass = hass
        self._entity_id = entity_id
        self._max_age_seconds = max_age_seconds
        self._continuity: CumulativeMeter | None = None

    async def read_liters(self) -> float:
        """Return the cumulative source value converted to liters."""
        raw_liters = await self.read_raw_liters()
        try:
            continuity = (
                CumulativeMeter.start(raw_liters=raw_liters)
                if self._continuity is None
                else self._continuity.update(raw_liters=raw_liters)
            )
        except ImplausibleMeterRegressionError as err:
            raise HomeAssistantError(
                f"Water meter {self._entity_id} reported an invalid decrease: {err}"
            ) from err
        self._continuity = continuity
        return self._continuity.total_liters

    async def read_raw_liters(self) -> float:
        """Return the source value in liters without continuity adjustment."""
        if self._entity_id is None:
            return 0.0
        state = self._hass.states.get(self._entity_id)
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            raise HomeAssistantError(f"Water meter {self._entity_id} is not available")
        if (
            self._max_age_seconds is not None
            and (datetime.now(UTC) - state.last_reported).total_seconds() > self._max_age_seconds
        ):
            raise HomeAssistantError(f"Water meter {self._entity_id} is stale")
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in VolumeConverter.VALID_UNITS:
            raise HomeAssistantError(f"Water meter {self._entity_id} has unsupported unit {unit!r}")
        try:
            value = float(state.state)
        except ValueError as err:
            raise HomeAssistantError(f"Water meter {self._entity_id} is not numeric") from err
        if not math.isfinite(value) or value < 0:
            raise HomeAssistantError(f"Water meter {self._entity_id} is not plausible")
        return VolumeConverter.convert(value, unit, UnitOfVolume.LITERS)


class HomeAssistantFlow:
    """Normalize an instantaneous HA flow sensor to liters per minute."""

    def __init__(self, hass: HomeAssistant, entity_id: str, max_age_seconds: float) -> None:
        """Initialize the flow adapter."""
        self._hass = hass
        self._entity_id = entity_id
        self._max_age_seconds = max_age_seconds

    async def read_l_min(self) -> float:
        """Return the current flow converted to liters per minute."""
        return self.read_state_l_min(self._hass.states.get(self._entity_id))

    def read_state_l_min(self, state: State | None) -> float:
        """Normalize one immutable HA event sample to liters per minute."""
        if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
            raise HomeAssistantError(f"Flow sensor {self._entity_id} is not available")
        age_seconds = (datetime.now(UTC) - state.last_reported).total_seconds()
        if age_seconds > self._max_age_seconds:
            raise HomeAssistantError(f"Flow sensor {self._entity_id} is stale")
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if unit not in VolumeFlowRateConverter.VALID_UNITS:
            raise HomeAssistantError(f"Flow sensor {self._entity_id} has unsupported unit {unit!r}")
        try:
            value = float(state.state)
        except ValueError as err:
            raise HomeAssistantError(f"Flow sensor {self._entity_id} is not numeric") from err
        if not math.isfinite(value) or value < 0:
            raise HomeAssistantError(f"Flow sensor {self._entity_id} is not plausible")
        return VolumeFlowRateConverter.convert(
            value,
            unit,
            UnitOfVolumeFlowRate.LITERS_PER_MINUTE,
        )


class HomeAssistantClock:
    """Use the event loop's cancellable monotonic sleep."""

    async def sleep(self, seconds: float) -> None:
        """Wait without blocking Home Assistant's event loop."""
        await asyncio.sleep(seconds)

    def monotonic(self) -> float:
        """Return the event loop's monotonic clock."""
        return asyncio.get_running_loop().time()
