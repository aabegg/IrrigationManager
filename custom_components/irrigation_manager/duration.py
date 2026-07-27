"""User-facing irrigation duration conversion."""

import math
import re
from collections.abc import Mapping

_DURATION_PATTERN = re.compile(
    r"^(?P<hours>\d+):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d(?:\.\d+)?)$"
)


def parse_duration(value: object) -> float:
    """Convert a selector value or compatible legacy value to seconds."""
    if isinstance(value, bool):
        raise ValueError("Duration must contain hours, minutes, and seconds")
    if isinstance(value, int | float):
        seconds = float(value)
    elif isinstance(value, Mapping):
        if not set(value).issubset({"hours", "minutes", "seconds"}):
            raise ValueError("Duration contains unsupported fields")
        try:
            hours = float(value.get("hours", 0))
            minutes = float(value.get("minutes", 0))
            remaining_seconds = float(value.get("seconds", 0))
        except TypeError, ValueError:
            raise ValueError("Duration fields must be numeric") from None
        if (
            not all(math.isfinite(part) for part in (hours, minutes, remaining_seconds))
            or hours < 0
            or not 0 <= minutes < 60
            or not 0 <= remaining_seconds < 60
        ):
            raise ValueError("Duration fields are out of range")
        seconds = hours * 3_600 + minutes * 60 + remaining_seconds
    elif isinstance(value, str):
        match = _DURATION_PATTERN.fullmatch(value.strip())
        if match is None:
            raise ValueError("Duration text is invalid")
        seconds = int(match["hours"]) * 3_600 + int(match["minutes"]) * 60 + float(match["seconds"])
    else:
        raise ValueError("Duration must contain hours, minutes, and seconds")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be positive")
    return seconds


def format_duration(seconds: float) -> dict[str, int | float]:
    """Format positive seconds for a duration selector without limiting hours."""
    seconds = parse_duration(seconds)
    hours = int(seconds // 3_600)
    remainder = seconds - hours * 3_600
    minutes = int(remainder // 60)
    remaining_seconds = remainder - minutes * 60
    return {
        "hours": hours,
        "minutes": minutes,
        "seconds": int(remaining_seconds) if remaining_seconds.is_integer() else remaining_seconds,
    }
