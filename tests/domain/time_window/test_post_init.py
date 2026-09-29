"""Tests for `domain.time_window.TimeWindow.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.time_window import TimeWindow

LONDON = ZoneInfo("Europe/London")


def test_both_bounds_are_optional() -> None:
    assert TimeWindow() == TimeWindow(None, None)


def test_aware_bounds_are_accepted() -> None:
    TimeWindow(time(8, 0, tzinfo=LONDON), time(16, 0, tzinfo=ZoneInfo("Asia/Tokyo")))


@pytest.mark.parametrize("start, end, name", [
    (time(8, 0), None, "start"),
    (None, time(16, 0), "end"),
    (time(8, 0, tzinfo=LONDON), time(16, 0), "end"),
])
def test_a_bound_without_a_timezone_is_rejected(start, end, name: str) -> None:
    with pytest.raises(ValueError, match=f"TimeWindow {name} .* has no timezone"):
        TimeWindow(start, end)
