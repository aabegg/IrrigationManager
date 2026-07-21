"""Deterministic fake Home Assistant irrigation plant for scenario tests."""

import asyncio
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.irrigation_manager.const import DOMAIN


class ControllableClock:
    """Drive monotonic and wall time independently without real waits."""

    def __init__(
        self,
        *,
        wall_time: datetime | None = None,
        auto_advance: bool = True,
        on_advance: Callable[[float], None] | None = None,
    ) -> None:
        self.elapsed = 0.0
        self.wall_time = wall_time or datetime(2026, 7, 21, 4, 0, tzinfo=UTC)
        self.auto_advance = auto_advance
        self.on_advance = on_advance
        self.sleeps: list[float] = []
        self.sleeping = asyncio.Event()
        self._waiters: list[tuple[float, asyncio.Future[None]]] = []

    async def sleep(self, seconds: float) -> None:
        """Advance immediately, or block until the test advances monotonic time."""
        seconds = max(0.0, seconds)
        self.sleeps.append(seconds)
        if self.auto_advance:
            self.advance(seconds)
            await asyncio.sleep(0)
            return
        if seconds == 0:
            await asyncio.sleep(0)
            return
        future = asyncio.get_running_loop().create_future()
        self._waiters.append((self.elapsed + seconds, future))
        self.sleeping.set()
        await future

    def monotonic(self) -> float:
        """Return deterministic elapsed time."""
        return self.elapsed

    def advance(self, seconds: float, *, advance_wall: bool = True) -> None:
        """Advance elapsed time and release waits whose target was reached."""
        if seconds < 0:
            raise ValueError("Monotonic time cannot move backwards")
        self.elapsed += seconds
        if advance_wall:
            self.wall_time += timedelta(seconds=seconds)
        if self.on_advance is not None:
            self.on_advance(seconds)
        remaining: list[tuple[float, asyncio.Future[None]]] = []
        for target, future in self._waiters:
            if target <= self.elapsed and not future.done():
                future.set_result(None)
            elif not future.done():
                remaining.append((target, future))
        self._waiters = remaining
        if not remaining:
            self.sleeping.clear()

    def jump_wall(self, delta: timedelta) -> None:
        """Simulate NTP, DST, or manual wall-clock changes only."""
        self.wall_time += delta


class FakeHaIrrigationPlant:
    """Model valves, feedback, water, weather, and HA state/service seams."""

    meter_entity_id = "sensor.irrigation_meter"
    flow_entity_id = "sensor.irrigation_flow"
    weather_entity_id = "weather.irrigation_test"

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        zone_flows_l_min: dict[str, float],
        main_valve: str | None = "switch.irrigation_main",
        auto_advance: bool = True,
    ) -> None:
        self.hass = hass
        self.zone_flows_l_min = zone_flows_l_min
        self.main_valve = main_valve
        self.clock = ControllableClock(auto_advance=auto_advance, on_advance=self._advance_water)
        self.open_valves: set[str] = set()
        self.operations: list[tuple[float, str, str]] = []
        self.maximum_simultaneous_zones = 0
        self.meter_liters = 0.0
        self.meter_fault: float | Exception | str | None = None
        self.meter_script: list[float | Exception] = []
        self.flow_override_l_min: float | Exception | None = None
        self.fail_open: set[str] = set()
        self.fail_close: set[str] = set()
        self.entry: MockConfigEntry | None = None
        self._register_hardware()

    @property
    def zone_valves(self) -> tuple[str, ...]:
        """Return every managed zone valve."""
        return tuple(self.zone_flows_l_min)

    def _register_hardware(self) -> None:
        async def turn_on(call: ServiceCall) -> None:
            await self.open(str(call.data["entity_id"]))

        async def turn_off(call: ServiceCall) -> None:
            await self.close(str(call.data["entity_id"]))

        self.hass.services.async_register("switch", "turn_on", turn_on)
        self.hass.services.async_register("switch", "turn_off", turn_off)
        for entity_id in self._all_valves():
            self.hass.states.async_set(entity_id, STATE_OFF)
        self._publish_meter()
        self.set_flow(0.0)
        self.set_weather("sunny", temperature=24.0, humidity=50.0)

    async def open(self, entity_id: str) -> None:
        """Apply an open command unless injected feedback remains closed."""
        self.operations.append((self.clock.monotonic(), "open", entity_id))
        if entity_id in self.fail_open:
            return
        self.open_valves.add(entity_id)
        self.hass.states.async_set(entity_id, STATE_ON)
        open_zones = self.open_valves.intersection(self.zone_valves)
        self.maximum_simultaneous_zones = max(
            self.maximum_simultaneous_zones,
            len(open_zones),
        )

    async def close(self, entity_id: str) -> None:
        """Apply a close command or inject stuck-open feedback."""
        self.operations.append((self.clock.monotonic(), "close", entity_id))
        if entity_id in self.fail_close:
            raise RuntimeError(f"{entity_id} remained open")
        self.open_valves.discard(entity_id)
        self.hass.states.async_set(entity_id, STATE_OFF)

    async def is_open(self, entity_id: str) -> bool:
        """Return physical feedback rather than command intent."""
        return entity_id in self.open_valves

    async def read_liters(self) -> float:
        """Return a cumulative reading or one injected meter fault."""
        if self.meter_script:
            reading = self.meter_script.pop(0)
            if isinstance(reading, Exception):
                raise reading
            return reading
        if isinstance(self.meter_fault, Exception):
            raise self.meter_fault
        if self.meter_fault == STATE_UNAVAILABLE:
            raise RuntimeError("water meter unavailable")
        if isinstance(self.meter_fault, float):
            return self.meter_fault
        return self.meter_liters

    async def read_l_min(self) -> float:
        """Return direct flow or the flow implied by currently open valves."""
        if isinstance(self.flow_override_l_min, Exception):
            raise self.flow_override_l_min
        if self.flow_override_l_min is not None:
            return self.flow_override_l_min
        return self._physical_flow_l_min()

    def set_flow(self, value: float | str) -> None:
        """Publish a normalized HA flow state for manager-level scenarios."""
        self.hass.states.async_set(
            self.flow_entity_id,
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolumeFlowRate.LITERS_PER_MINUTE},
        )

    def set_meter(self, value: float | str) -> None:
        """Set and publish the raw cumulative meter state."""
        if isinstance(value, float | int):
            self.meter_liters = float(value)
        self.hass.states.async_set(
            self.meter_entity_id,
            str(value),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
        )

    def set_meter_unavailable(self) -> None:
        """Publish unavailable cumulative-meter state."""
        self.hass.states.async_set(
            self.meter_entity_id,
            STATE_UNAVAILABLE,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
        )

    def set_weather(self, condition: str, **attributes: float) -> None:
        """Publish deterministic native weather context."""
        self.hass.states.async_set(self.weather_entity_id, condition, attributes)

    async def setup_entry(
        self,
        *,
        with_meter: bool = True,
        with_flow: bool = True,
        installation_data: dict[str, Any] | None = None,
        zone_data: Iterable[dict[str, Any]] | None = None,
        unique_id: str = "qualification-installation",
    ) -> MockConfigEntry:
        """Set up a persisted integration entry backed by this fake plant."""
        data: dict[str, Any] = {"name": "Qualification irrigation"}
        if self.main_valve is not None:
            data["main_valve"] = self.main_valve
        if with_meter:
            data["water_meter"] = self.meter_entity_id
        if with_flow:
            data["flow_sensor"] = self.flow_entity_id
        data["weather_entity"] = self.weather_entity_id
        data.update(installation_data or {})
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Qualification irrigation",
            data=data,
            unique_id=unique_id,
        )
        entry.add_to_hass(self.hass)
        specs = list(zone_data or ({},) * len(self.zone_valves))
        for index, (valve, overrides) in enumerate(
            zip(self.zone_valves, specs, strict=True), start=1
        ):
            subentry = ConfigSubentry(
                data=MappingProxyType(
                    {
                        "name": f"Zone {index}",
                        "zone_valve": valve,
                        "default_duration": 60,
                        "min_flow": self.zone_flows_l_min[valve] * 0.5,
                        "max_flow": self.zone_flows_l_min[valve] * 1.5,
                        "flow_grace_seconds": 0,
                        **overrides,
                    }
                ),
                subentry_id=f"qualification-zone-{index}",
                subentry_type="zone",
                title=f"Zone {index}",
                unique_id=f"qualification-zone-{index}",
            )
            self.hass.config_entries.async_add_subentry(entry, subentry)
        assert await self.hass.config_entries.async_setup(entry.entry_id)
        await self.hass.async_block_till_done()
        self.entry = entry
        return entry

    async def restart(self) -> MockConfigEntry:
        """Unload and reload the entry while preserving HA storage."""
        if self.entry is None:
            raise RuntimeError("Plant entry is not set up")
        assert await self.hass.config_entries.async_unload(self.entry.entry_id)
        assert await self.hass.config_entries.async_setup(self.entry.entry_id)
        await self.hass.async_block_till_done()
        return self.entry

    def force_feedback(self, entity_id: str, *, open_: bool) -> None:
        """Inject an unsolicited physical valve feedback transition."""
        if open_:
            self.open_valves.add(entity_id)
            self.hass.states.async_set(entity_id, STATE_ON)
        else:
            self.open_valves.discard(entity_id)
            self.hass.states.async_set(entity_id, STATE_OFF)

    def _advance_water(self, seconds: float) -> None:
        self.meter_liters += self._physical_flow_l_min() * seconds / 60
        self._publish_meter()
        self.set_flow(self._physical_flow_l_min())

    def _physical_flow_l_min(self) -> float:
        if self.main_valve is not None and self.main_valve not in self.open_valves:
            return 0.0
        return sum(
            flow for valve, flow in self.zone_flows_l_min.items() if valve in self.open_valves
        )

    def _publish_meter(self) -> None:
        self.hass.states.async_set(
            self.meter_entity_id,
            str(self.meter_liters),
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.LITERS},
        )

    def _all_valves(self) -> tuple[str, ...]:
        return (*self.zone_valves, *((self.main_valve,) if self.main_valve else ()))
