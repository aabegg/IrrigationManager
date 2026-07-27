"""User-facing irrigation duration conversion."""

import math
import re

_DURATION_PATTERN = re.compile(
    r"^(?P<hours>\d+):(?P<minutes>[0-5]\d):(?P<seconds>[0-5]\d(?:\.\d+)?)$"
)


def parse_duration(value: object) -> float:
    """Convert HH:MM:SS text or compatible numeric seconds to seconds."""
    if isinstance(value, bool):
        raise ValueError("Duration must use HH:MM:SS")
    if isinstance(value, int | float):
        seconds = float(value)
    elif isinstance(value, str):
        match = _DURATION_PATTERN.fullmatch(value.strip())
        if match is None:
            raise ValueError("Duration must use HH:MM:SS")
        seconds = int(match["hours"]) * 3_600 + int(match["minutes"]) * 60 + float(match["seconds"])
    else:
        raise ValueError("Duration must use HH:MM:SS")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Duration must be positive")
    return seconds


def format_duration(seconds: float) -> str:
    """Format positive seconds as HH:MM:SS without limiting total hours."""
    seconds = parse_duration(seconds)
    hours = int(seconds // 3_600)
    remainder = seconds - hours * 3_600
    minutes = int(remainder // 60)
    remaining_seconds = remainder - minutes * 60
    if remaining_seconds.is_integer():
        seconds_text = f"{int(remaining_seconds):02d}"
    else:
        seconds_text = f"{remaining_seconds:09.6f}".rstrip("0").rstrip(".")
        if remaining_seconds < 10:
            seconds_text = f"0{seconds_text}"
    return f"{hours:02d}:{minutes:02d}:{seconds_text}"
