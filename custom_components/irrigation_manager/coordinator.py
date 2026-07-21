"""Push coordinator for Irrigation Manager entities."""

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .models import InstallationSnapshot


class IrrigationCoordinator(DataUpdateCoordinator[InstallationSnapshot]):
    """Publish atomic snapshots to all installation entities."""

    def set_snapshot(self, snapshot: InstallationSnapshot) -> None:
        """Publish a new immutable snapshot."""
        self.async_set_updated_data(snapshot)
