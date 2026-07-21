"""Runtime models shared by the Home Assistant platforms."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InstallationSnapshot:
    """Current published state of one irrigation installation."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    status: str = "idle"
    active_zone_id: str | None = None


@dataclass(frozen=True, slots=True)
class StoredInstallationState:
    """Versioned critical state persisted independently of entities."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    emergency_stop: bool = False

    @staticmethod
    def _float(value: object) -> float:
        """Return numeric JSON values without silently discarding corruption."""
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Stored irrigation total is not numeric")
        return float(value)

    @classmethod
    def from_dict(cls, data: dict[str, object] | None) -> StoredInstallationState:
        """Deserialize storage data with safe defaults."""
        if data is None:
            return cls()
        raw_zone_totals = data.get("zone_totals_liters", {})
        if not isinstance(raw_zone_totals, dict):
            raise ValueError("Stored zone totals are malformed")
        zone_totals = {str(key): cls._float(value) for key, value in raw_zone_totals.items()}
        raw_quality = data.get("zone_measurement_quality", {})
        if not isinstance(raw_quality, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_quality.items()
        ):
            raise ValueError("Stored measurement quality is malformed")
        emergency_stop = data.get("emergency_stop", False)
        if not isinstance(emergency_stop, bool):
            raise ValueError("Stored emergency stop is not boolean")
        return cls(
            installation_total_liters=cls._float(data.get("installation_total_liters", 0.0)),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=dict(raw_quality),
            unassigned_total_liters=cls._float(data.get("unassigned_total_liters", 0.0)),
            emergency_stop=emergency_stop,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize state to JSON-compatible storage data."""
        return {
            "installation_total_liters": self.installation_total_liters,
            "zone_totals_liters": self.zone_totals_liters,
            "zone_measurement_quality": self.zone_measurement_quality,
            "unassigned_total_liters": self.unassigned_total_liters,
            "emergency_stop": self.emergency_stop,
        }
