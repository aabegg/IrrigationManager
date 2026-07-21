"""Versioned Home Assistant storage for critical irrigation state."""

from typing import override

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import StoredInstallationState

STORAGE_VERSION = 1
STORAGE_MINOR_VERSION = 3


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
        if old_major_version == 1 and old_minor_version in {1, 2}:
            migrated = dict(old_data)
            if old_minor_version == 1:
                migrated["active_execution"] = None
            migrated["zone_last_delivered_liters"] = {}
            migrated["zone_last_duration_seconds"] = {}
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
