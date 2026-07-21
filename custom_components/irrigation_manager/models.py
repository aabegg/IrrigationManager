"""Runtime models shared by the Home Assistant platforms."""

from dataclasses import dataclass, field
from typing import cast


@dataclass(frozen=True, slots=True)
class ManualIrrigationRequest:
    """Durable manual irrigation order with an immutable zone snapshot."""

    request_id: str
    sequence: int
    zone_id: str
    zone_subentry_id: str
    zone_name: str
    zone_valve: str
    main_valve: str | None
    target_type: str
    target_value: float
    remaining_value: float
    created_at: str
    expires_at: str
    status: str = "pending"
    source: str = "manual"
    execution_id: str | None = None
    hard_time_limit_seconds: float | None = None
    max_dose_value: float | None = None
    soak_duration_seconds: float = 0.0
    soak_until: str | None = None
    meter_failure_strategy: str = "abort"
    estimated_flow_l_min: float | None = None
    minimum_flow_l_min: float | None = None
    maximum_flow_l_min: float | None = None
    flow_grace_seconds: float = 5.0
    revision: int = 1

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> ManualIrrigationRequest:
        """Deserialize one persisted manual order."""
        required_strings = (
            "request_id",
            "zone_id",
            "zone_subentry_id",
            "zone_name",
            "zone_valve",
            "target_type",
            "created_at",
            "expires_at",
        )
        if not all(isinstance(data.get(key), str) for key in required_strings):
            raise ValueError("Stored manual irrigation request is malformed")
        main_valve = data.get("main_valve")
        execution_id = data.get("execution_id")
        soak_until = data.get("soak_until")
        status = data.get("status", "pending")
        source = data.get("source", "manual")
        if (
            not all(
                value is None or isinstance(value, str)
                for value in (main_valve, execution_id, soak_until)
            )
            or not isinstance(status, str)
            or not isinstance(source, str)
        ):
            raise ValueError("Stored manual irrigation request metadata is malformed")
        main_valve = cast(str | None, main_valve)
        execution_id = cast(str | None, execution_id)
        soak_until = cast(str | None, soak_until)
        return cls(
            request_id=str(data["request_id"]),
            sequence=int(StoredInstallationState._float(data.get("sequence"))),
            zone_id=str(data["zone_id"]),
            zone_subentry_id=str(data["zone_subentry_id"]),
            zone_name=str(data["zone_name"]),
            zone_valve=str(data["zone_valve"]),
            main_valve=main_valve,
            target_type=str(data["target_type"]),
            target_value=StoredInstallationState._float(data.get("target_value")),
            remaining_value=StoredInstallationState._float(data.get("remaining_value")),
            created_at=str(data["created_at"]),
            expires_at=str(data["expires_at"]),
            status=status,
            source=source,
            execution_id=execution_id,
            hard_time_limit_seconds=_optional_stored_float(data, "hard_time_limit_seconds"),
            max_dose_value=_optional_stored_float(data, "max_dose_value"),
            soak_duration_seconds=StoredInstallationState._float(
                data.get("soak_duration_seconds", 0.0)
            ),
            soak_until=soak_until,
            meter_failure_strategy=(
                str(data["meter_failure_strategy"])
                if isinstance(data.get("meter_failure_strategy"), str)
                else "abort"
            ),
            estimated_flow_l_min=_optional_stored_float(data, "estimated_flow_l_min"),
            minimum_flow_l_min=_optional_stored_float(data, "minimum_flow_l_min"),
            maximum_flow_l_min=_optional_stored_float(data, "maximum_flow_l_min"),
            flow_grace_seconds=StoredInstallationState._float(data.get("flow_grace_seconds", 5.0)),
            revision=int(StoredInstallationState._float(data.get("revision", 1))),
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one manual order."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class IrrigationExecutionState:
    """Durable lifecycle of one accepted irrigation order."""

    execution_id: str
    request_id: str
    zone_id: str
    target_type: str
    target_value: float
    remaining_value: float
    status: str
    created_at: str
    dose_number: int = 0
    delivered_liters: float = 0.0
    delivered_duration_seconds: float = 0.0
    ended_at: str | None = None
    result: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> IrrigationExecutionState:
        """Deserialize one persisted execution."""
        strings = ("execution_id", "request_id", "zone_id", "target_type", "status", "created_at")
        if not all(isinstance(data.get(key), str) for key in strings):
            raise ValueError("Stored irrigation execution is malformed")
        ended_at = data.get("ended_at")
        result = data.get("result")
        if not all(value is None or isinstance(value, str) for value in (ended_at, result)):
            raise ValueError("Stored irrigation execution result is malformed")
        ended_at = cast(str | None, ended_at)
        result = cast(str | None, result)
        return cls(
            execution_id=str(data["execution_id"]),
            request_id=str(data["request_id"]),
            zone_id=str(data["zone_id"]),
            target_type=str(data["target_type"]),
            target_value=StoredInstallationState._float(data.get("target_value")),
            remaining_value=StoredInstallationState._float(data.get("remaining_value")),
            status=str(data["status"]),
            created_at=str(data["created_at"]),
            dose_number=int(StoredInstallationState._float(data.get("dose_number", 0))),
            delivered_liters=StoredInstallationState._float(data.get("delivered_liters", 0.0)),
            delivered_duration_seconds=StoredInstallationState._float(
                data.get("delivered_duration_seconds", 0.0)
            ),
            ended_at=ended_at,
            result=result,
        )

    def as_dict(self) -> dict[str, object]:
        """Serialize one irrigation execution."""
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


def _optional_stored_float(data: dict[str, object], key: str) -> float | None:
    """Read one optional persisted number."""
    value = data.get(key)
    return None if value is None else StoredInstallationState._float(value)


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
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    status: str = "idle"
    active_zone_id: str | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    active_target_type: str | None = None
    active_target_value: float | None = None
    active_remaining_value: float | None = None
    active_measurement_quality: str | None = None
    pending_request_count: int = 0
    current_dose_number: int | None = None
    active_request_id: str | None = None
    active_execution_id: str | None = None


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
    requested_amount_liters: float | None = None
    hard_time_limit_seconds: float | None = None
    meter_failure_strategy: str = "abort"
    zone_opening_at: str | None = None
    fallback_started_at: str | None = None
    fallback_checkpoint_at: str | None = None
    delivered_liters_at_fallback: float = 0.0
    request_id: str | None = None
    execution_id: str | None = None
    dose_number: int = 1
    dose_target_value: float | None = None

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
            requested_amount_liters=optional_float("requested_amount_liters"),
            hard_time_limit_seconds=optional_float("hard_time_limit_seconds"),
            meter_failure_strategy=(
                required_string("meter_failure_strategy")
                if "meter_failure_strategy" in data
                else "abort"
            ),
            zone_opening_at=optional_string("zone_opening_at"),
            fallback_started_at=optional_string("fallback_started_at"),
            fallback_checkpoint_at=optional_string("fallback_checkpoint_at"),
            delivered_liters_at_fallback=StoredInstallationState._float(
                data.get("delivered_liters_at_fallback", 0.0)
            ),
            request_id=optional_string("request_id"),
            execution_id=optional_string("execution_id"),
            dose_number=int(StoredInstallationState._float(data.get("dose_number", 1))),
            dose_target_value=optional_float("dose_target_value"),
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
            "requested_amount_liters": self.requested_amount_liters,
            "hard_time_limit_seconds": self.hard_time_limit_seconds,
            "meter_failure_strategy": self.meter_failure_strategy,
            "zone_opening_at": self.zone_opening_at,
            "fallback_started_at": self.fallback_started_at,
            "fallback_checkpoint_at": self.fallback_checkpoint_at,
            "delivered_liters_at_fallback": self.delivered_liters_at_fallback,
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "dose_number": self.dose_number,
            "dose_target_value": self.dose_target_value,
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
    unassigned_measurement_quality: str = "unknown"
    unassigned_measurement_origin: str = "unknown"
    idle_meter_raw_baseline_liters: float | None = None
    emergency_stop: bool = False
    installation_safety_lock: str | None = None
    active_execution: ActiveExecutionState | None = None
    manual_requests: tuple[ManualIrrigationRequest, ...] = ()
    irrigation_executions: tuple[IrrigationExecutionState, ...] = ()
    next_request_sequence: int = 1

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
        raw_requests = data.get("manual_requests", [])
        raw_executions = data.get("irrigation_executions", [])
        if not isinstance(raw_requests, list) or not all(
            isinstance(item, dict) for item in raw_requests
        ):
            raise ValueError("Stored manual irrigation requests are malformed")
        if not isinstance(raw_executions, list) or not all(
            isinstance(item, dict) for item in raw_executions
        ):
            raise ValueError("Stored irrigation executions are malformed")
        unassigned_quality = data.get("unassigned_measurement_quality", "unknown")
        unassigned_origin = data.get("unassigned_measurement_origin", "unknown")
        if not isinstance(unassigned_quality, str) or not isinstance(unassigned_origin, str):
            raise ValueError("Stored unassigned measurement metadata is malformed")
        raw_idle_baseline = data.get("idle_meter_raw_baseline_liters")
        idle_baseline = None if raw_idle_baseline is None else cls._float(raw_idle_baseline)
        return cls(
            installation_total_liters=cls._float(data.get("installation_total_liters", 0.0)),
            zone_totals_liters=zone_totals,
            zone_measurement_quality=dict(raw_quality),
            zone_last_delivered_liters=last_delivered,
            zone_last_duration_seconds=last_duration,
            zone_safety_locks=dict(raw_zone_locks),
            unassigned_total_liters=cls._float(data.get("unassigned_total_liters", 0.0)),
            unassigned_measurement_quality=unassigned_quality,
            unassigned_measurement_origin=unassigned_origin,
            idle_meter_raw_baseline_liters=idle_baseline,
            emergency_stop=emergency_stop,
            installation_safety_lock=installation_lock,
            active_execution=(
                ActiveExecutionState.from_dict(raw_active_execution)
                if raw_active_execution is not None
                else None
            ),
            manual_requests=tuple(ManualIrrigationRequest.from_dict(item) for item in raw_requests),
            irrigation_executions=tuple(
                IrrigationExecutionState.from_dict(item) for item in raw_executions
            ),
            next_request_sequence=int(
                cls._float(data.get("next_request_sequence", len(raw_requests) + 1))
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
            "unassigned_measurement_quality": self.unassigned_measurement_quality,
            "unassigned_measurement_origin": self.unassigned_measurement_origin,
            "idle_meter_raw_baseline_liters": self.idle_meter_raw_baseline_liters,
            "emergency_stop": self.emergency_stop,
            "installation_safety_lock": self.installation_safety_lock,
            "active_execution": (
                self.active_execution.as_dict() if self.active_execution is not None else None
            ),
            "manual_requests": [request.as_dict() for request in self.manual_requests],
            "irrigation_executions": [
                execution.as_dict() for execution in self.irrigation_executions
            ],
            "next_request_sequence": self.next_request_sequence,
        }
