"""User-facing duration conversion tests."""

import pytest

from custom_components.irrigation_manager.duration import format_duration, parse_duration


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00:10:00", 600),
        ("01:02:03", 3_723),
        ("168:00:00", 604_800),
        ("00:00:00.5", 0.5),
        ({"hours": 1, "minutes": 2, "seconds": 3}, 3_723),
        ({"hours": 168, "minutes": 0, "seconds": 0}, 604_800),
        (600, 600),
    ],
)
def test_parse_duration(value: object, expected: float) -> None:
    """Accept HH:MM:SS while retaining numeric service compatibility."""
    assert parse_duration(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "10:00",
        "01:60:00",
        "01:00:60",
        "seconds",
        {"hours": 1, "minutes": 60, "seconds": 0},
        {"days": 1},
        0,
        True,
    ],
)
def test_parse_duration_rejects_invalid_values(value: object) -> None:
    """Reject ambiguous or non-positive durations."""
    with pytest.raises(ValueError, match="Duration"):
        parse_duration(value)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (600, {"hours": 0, "minutes": 10, "seconds": 0}),
        (3_723, {"hours": 1, "minutes": 2, "seconds": 3}),
        (604_800, {"hours": 168, "minutes": 0, "seconds": 0}),
    ],
)
def test_format_duration(seconds: float, expected: dict[str, int | float]) -> None:
    """Format persisted seconds for structured fields without a 24-hour ceiling."""
    assert format_duration(seconds) == expected
