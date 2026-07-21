"""Water-meter normalization and continuity."""

import math
from dataclasses import dataclass, replace

RESET_ORIGIN_MAX_LITERS = 10.0
RESET_MINIMUM_DROP_LITERS = 5.0
RESET_DROP_TO_NEW_VALUE_RATIO = 5.0


class ImplausibleMeterRegressionError(ValueError):
    """Raised when a decrease is not sufficiently reset-like to accept."""


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
        normalized = cls._validate_raw(raw_liters)
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
        normalized = self._validate_raw(raw_liters)
        did_reset = normalized < self.last_raw_liters
        if did_reset and not self._is_plausible_reset(normalized):
            raise ImplausibleMeterRegressionError(
                f"Water meter regressed from {self.last_raw_liters:g} L to {normalized:g} L "
                "without a plausible source reset"
            )
        delta_liters = normalized if did_reset else normalized - self.last_raw_liters
        return replace(
            self,
            accumulated_liters=self.accumulated_liters + delta_liters,
            last_raw_liters=normalized,
            reset_count=self.reset_count + int(did_reset),
        )

    def _is_plausible_reset(self, new_raw_liters: float) -> bool:
        """Classify only a large drop back near the source origin as a reset."""
        drop_liters = self.last_raw_liters - new_raw_liters
        return (
            new_raw_liters <= RESET_ORIGIN_MAX_LITERS
            and drop_liters >= RESET_MINIMUM_DROP_LITERS
            and drop_liters >= new_raw_liters * RESET_DROP_TO_NEW_VALUE_RATIO
        )

    @staticmethod
    def _validate_raw(raw_liters: float) -> float:
        """Reject values that cannot represent a cumulative physical meter."""
        if not math.isfinite(raw_liters) or raw_liters < 0:
            raise ValueError("Water meter reading is not plausible")
        return raw_liters

    def correct(self, *, physical_total_liters: float) -> CumulativeMeter:
        """Apply a future-facing offset without rewriting accumulated use."""
        return replace(
            self,
            correction_liters=physical_total_liters - self.accumulated_liters,
        )
