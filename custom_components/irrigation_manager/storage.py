"""Versioned Home Assistant storage for critical irrigation state."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .models import StoredInstallationState

STORAGE_VERSION = 1


class IrrigationStore:
    """Persist one irrigation installation independently of entity restore."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize storage isolated by config entry ID."""
        self._store = Store[dict[str, object]](
            hass,
            STORAGE_VERSION,
            f"irrigation_manager.{entry_id}",
            atomic_writes=True,
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
