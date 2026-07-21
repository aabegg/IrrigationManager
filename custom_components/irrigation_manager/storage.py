"""Versioned Home Assistant storage for critical irrigation state."""

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import StoredInstallationState

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 9


class _StateStore(Store[dict[str, object]]):
    """Migrate durable irrigation state between additive schema revisions."""

    @override
    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, object],
    ) -> dict[str, object]:
        """Add fields introduced by additive 1.x schema revisions."""
        if old_major_version == 1 and old_minor_version in {1, 2, 3, 4, 5, 6, 7, 8}:
            migrated = dict(old_data)
            if old_minor_version == 1:
                migrated["active_execution"] = None
            if old_minor_version < 3:
                migrated["zone_last_delivered_liters"] = {}
                migrated["zone_last_duration_seconds"] = {}
            if old_minor_version < 4:
                migrated["zone_safety_locks"] = {}
            if old_minor_version < 5:
                migrated["installation_safety_lock"] = None
            if old_minor_version < 6:
                migrated["unassigned_measurement_quality"] = "unknown"
                migrated["unassigned_measurement_origin"] = "unknown"
                migrated["idle_meter_raw_baseline_liters"] = None
            if old_minor_version == 6:
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    raw_active = dict(raw_active)
                    raw_active["requested_amount_liters"] = None
                    raw_active["hard_time_limit_seconds"] = None
                    raw_active["meter_failure_strategy"] = "abort"
                    raw_active["zone_opening_at"] = None
                    raw_active["fallback_started_at"] = None
                    raw_active["fallback_checkpoint_at"] = None
                    raw_active["delivered_liters_at_fallback"] = 0.0
                    migrated["active_execution"] = raw_active
            if old_minor_version < 8:
                migrated["manual_requests"] = []
                migrated["irrigation_executions"] = []
                migrated["next_request_sequence"] = 1
                raw_active = migrated.get("active_execution")
                if isinstance(raw_active, dict):
                    raw_active = dict(raw_active)
                    raw_active["request_id"] = None
                    raw_active["execution_id"] = None
                    raw_active["dose_number"] = 1
                    raw_active["dose_target_value"] = None
                    migrated["active_execution"] = raw_active
            if old_minor_version < 9:
                raw_requests = migrated.get("manual_requests", [])
                if isinstance(raw_requests, list):
                    migrated["manual_requests"] = [
                        {**request, "revision": 1} if isinstance(request, dict) else request
                        for request in raw_requests
                    ]
            return migrated
        raise NotImplementedError


class IrrigationStore:
    """Persist one irrigation installation independently of entity restore."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage isolated by config entry ID."""
        self._store = _StateStore(
            hass,
            STORAGE_VERSION,
            f"irrigation_manager.{entry_id}",
            atomic_writes=True,
            minor_version=STORAGE_MINOR_VERSION,
        )

    async def async_load(self) -> StoredInstallationState:
        """Load the installation state or return a clean initial state."""
        return StoredInstallationState.from_dict(await self._store.async_load())

    async def async_save(self, state: StoredInstallationState) -> None:
        """Atomically persist a critical state transition."""
        await self._store.async_save(state.as_dict())

    async def async_remove(self) -> None:
        """Remove storage after the config entry is deleted."""
        await self._store.async_remove()
