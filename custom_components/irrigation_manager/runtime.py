"""Typed Config Entry runtime data."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .coordinator import IrrigationCoordinator
from .manager import IrrigationManager
from .storage import IrrigationStore


@dataclass(slots=True)
class IrrigationRuntimeData:
    """Runtime objects owned by one config entry."""

    coordinator: IrrigationCoordinator
    store: IrrigationStore
    manager: IrrigationManager


type IrrigationConfigEntry = ConfigEntry[IrrigationRuntimeData]
