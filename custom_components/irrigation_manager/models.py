"""Runtime models shared by the Home Assistant platforms."""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InstallationSnapshot:
    """Current published state of one irrigation installation."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    zone_safety_locks: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    status: str = "idle"
    active_zone_id: str | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None


@dataclass(frozen=True, slots=True)
class ActiveExecutionState:
    """Minimum durable state needed to recover an interrupted dose."""

    zone_id: str
    zone_valve: str
    main_valve: str | None
    meter_raw_baseline_liters: float | None
    prepared_at: str
    watering_started_at: str | None
    requested_duration_seconds: float
    estimated_flow_l_min: float | None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ActiveExecutionState:
        """Deserialize and validate an active execution record."""

        def required_string(key: str) -> str:
            value = data.get(key)
            if not isinstance(value, str):
                raise ValueError(f"Stored active execution {key} is malformed")
            return value

        def optional_string(key: str) -> str | None:
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError(f"Stored active execution {key} is malformed")
            return value

        def optional_float(key: str) -> float | None:
            value = data.get(key)
            if value is None:
                return None
            return StoredInstallationState._float(value)

        return cls(
            zone_id=required_string("zone_id"),
            zone_valve=required_string("zone_valve"),
            main_valve=optional_string("main_valve"),
            meter_raw_baseline_liters=optional_float("meter_raw_baseline_liters"),
            prepared_at=required_string("prepared_at"),
            watering_started_at=optional_string("watering_started_at"),
            requested_duration_seconds=StoredInstallationState._float(
                data.get("requested_duration_seconds")
            ),
            estimated_flow_l_min=optional_float("estimated_flow_l_min"),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize the active execution for Home Assistant storage."""
        return {
            "zone_id": self.zone_id,
            "zone_valve": self.zone_valve,
            "main_valve": self.main_valve,
            "meter_raw_baseline_liters": self.meter_raw_baseline_liters,
            "prepared_at": self.prepared_at,
            "watering_started_at": self.watering_started_at,
            "requested_duration_seconds": self.requested_duration_seconds,
            "estimated_flow_l_min": self.estimated_flow_l_min,
        }


@dataclass(frozen=True, slots=True)
class StoredInstallationState:
    """Versioned critical state persisted independently of entities."""

    installation_total_liters: float = 0.0
    zone_totals_liters: dict[str, float] = field(default_factory=dict)
    zone_measurement_quality: dict[str, str] = field(default_factory=dict)
    zone_last_delivered_liters: dict[str, float] = field(default_factory=dict)
    zone_last_duration_seconds: dict[str, float] = field(default_factory=dict)
    zone_safety_locks: dict[str, str] = field(default_factory=dict)
    unassigned_total_liters: float = 0.0
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    active_execution: ActiveExecutionState | None = None

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
        raw_last_delivered = data.get("zone_last_delivered_liters", {})
        if not isinstance(raw_last_delivered, dict):
            raise ValueError("Stored last delivered amounts are malformed")
        last_delivered = {str(key): cls._float(value) for key, value in raw_last_delivered.items()}
        raw_last_duration = data.get("zone_last_duration_seconds", {})
        if not isinstance(raw_last_duration, dict):
            raise ValueError("Stored last delivery durations are malformed")
        last_duration = {str(key): cls._float(value) for key, value in raw_last_duration.items()}
        raw_quality = data.get("zone_measurement_quality", {})
        if not isinstance(raw_quality, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_quality.items()
        ):
            raise ValueError("Stored measurement quality is malformed")
        raw_zone_locks = data.get("zone_safety_locks", {})
        if not isinstance(raw_zone_locks, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in raw_zone_locks.items()
        ):
            raise ValueError("Stored zone safety locks are malformed")
        emergency_stop = data.get("emergency_stop", False)
        if not isinstance(emergency_stop, bool):
            raise ValueError("Stored emergency stop is not boolean")
        installation_lock = data.get("installation_safety_lock")
        if installation_lock is not None and not isinstance(installation_lock, str):
            raise ValueError("Stored installation safety lock is malformed")
        raw_active_execution = data.get("active_execution")
        if raw_active_execution is not None and not isinstance(raw_active_execution, dict):
            raise ValueError("Stored active execution is malformed")
        return cls(
            installation_total_liters=cls._float(data.get("installation_total_liters", 0.0)),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=dict(raw_quality),
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            zone_safety_locks=dict(raw_zone_locks),
            unassigned_total_liters=cls._float(data.get("unassigned_total_liters", 0.0)),
            emergency_stop=emergency_stop,
            installation_safety_lock=installation_lock,
            active_execution=(
                ActiveExecutionState.from_dict(raw_active_execution)
                if raw_active_execution is not None
                else None
            ),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize state to JSON-compatible storage data."""
        return {
            "installation_total_liters": self.installation_total_liters,
            "zone_totals_liters": self.zone_totals_liters,
            "zone_measurement_quality": self.zone_measurement_quality,
            "zone_last_delivered_liters": self.zone_last_delivered_liters,
            "zone_last_duration_seconds": self.zone_last_duration_seconds,
            "zone_safety_locks": self.zone_safety_locks,
            "unassigned_total_liters": self.unassigned_total_liters,
            "emergency_stop": self.emergency_stop,
            "installation_safety_lock": self.installation_safety_lock,
            "active_execution": (
                self.active_execution.as_dict() if self.active_execution is not None else None
            ),
        }
