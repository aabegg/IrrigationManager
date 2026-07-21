"""Water-meter normalization and continuity."""

from dataclasses import dataclass, replace


@dataclass(frozen=True, slots=True)
class CumulativeMeter:
    """A monotonic internal total backed by a source that may reset."""

    accumulated_liters: float
    last_raw_liters: float
    correction_liters: float = 0.0
    reset_count: int = 0

    @classmethod
    def start(cls, *, raw_liters: float) -> CumulativeMeter:
        """Initialize continuity from the source's current total."""
        normalized = max(0.0, raw_liters)
        return cls(
            accumulated_liters=normalized,
            last_raw_liters=normalized,
        )

    @property
    def total_liters(self) -> float:
        """Return the corrected current physical meter total."""
        return self.accumulated_liters + self.correction_liters

    def update(self, *, raw_liters: float) -> CumulativeMeter:
        """Apply a source reading, preserving continuity across source resets."""
        normalized = max(0.0, raw_liters)
        did_reset = normalized < self.last_raw_liters
        delta_liters = normalized if did_reset else normalized - self.last_raw_liters
        return replace(
            self,
            accumulated_liters=self.accumulated_liters + delta_liters,
            last_raw_liters=normalized,
            reset_count=self.reset_count + int(did_reset),
        )

    def correct(self, *, physical_total_liters: float) -> CumulativeMeter:
        """Apply a future-facing offset without rewriting accumulated use."""
        return replace(
            self,
            correction_liters=physical_total_liters - self.accumulated_liters,
        )
