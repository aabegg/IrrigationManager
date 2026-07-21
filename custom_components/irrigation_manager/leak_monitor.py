"""Domain model for confirming and measuring idle flow."""

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class ConfirmedLeak:
    """A continuous above-threshold idle-flow observation."""

    duration_seconds: float
    integrated_liters: float


@dataclass(frozen=True, slots=True)
class LeakObservation:
    """Integrate event-driven flow samples over one continuous observation."""

    started_at: float
    last_observed_at: float
    last_flow_l_min: float
    integrated_liters: float = 0.0

    @classmethod
    def start(cls, *, at: float, flow_l_min: float) -> LeakObservation:
        """Start observing an above-threshold flow sample."""
        return cls(started_at=at, last_observed_at=at, last_flow_l_min=flow_l_min)

    def observe(self, *, at: float, flow_l_min: float) -> LeakObservation:
        """Integrate up to a new event sample using the preceding rate."""
        elapsed = max(0.0, at - self.last_observed_at)
        return replace(
            self,
            last_observed_at=max(at, self.last_observed_at),
            last_flow_l_min=flow_l_min,
            integrated_liters=self.integrated_liters + self.last_flow_l_min * elapsed / 60,
        )

    def confirm(self, *, at: float, minimum_duration_seconds: float) -> ConfirmedLeak | None:
        """Confirm only observations lasting for the configured minimum duration."""
        duration = max(0.0, at - self.started_at)
        if duration < minimum_duration_seconds:
            return None
        elapsed = max(0.0, at - self.last_observed_at)
        return ConfirmedLeak(
            duration_seconds=duration,
            integrated_liters=(self.integrated_liters + self.last_flow_l_min * elapsed / 60),
        )
