"""Tests for `domain.time_window.TimeWindow.contains`."""

from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.time_window import TimeWindow

LONDON = ZoneInfo("Europe/London")
TOKYO = ZoneInfo("Asia/Tokyo")


def london(hour: int, minute: int = 0) -> time:
    return time(hour, minute, tzinfo=LONDON)


def utc(month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=UTC)


def test_start_is_inclusive_and_end_exclusive() -> None:
    window = TimeWindow(london(8), london(16))

    assert window.contains(utc(1, 5, 8, 0))
    assert window.contains(utc(1, 5, 15, 59))
    assert not window.contains(utc(1, 5, 7, 59))
    assert not window.contains(utc(1, 5, 16, 0))


def test_bounds_follow_their_zone_across_dst() -> None:
    window = TimeWindow(london(8), london(16))

    assert not window.contains(utc(7, 6, 15, 30))     # 16:30 London in summer (BST)
    assert window.contains(utc(1, 5, 15, 30))         # 15:30 London in winter (GMT)
    assert window.contains(utc(7, 6, 7, 0))           # 08:00 London in summer
    assert not window.contains(utc(1, 5, 7, 0))       # 07:00 London in winter


def test_instant_on_another_clock_is_compared_as_the_same_moment() -> None:
    window = TimeWindow(london(8), london(16))

    assert window.contains(datetime(2026, 1, 5, 10, 0, tzinfo=BROKER_SERVER_TZ))       # 08:00 London
    assert not window.contains(datetime(2026, 1, 5, 9, 55, tzinfo=BROKER_SERVER_TZ))   # 07:55 London


def test_end_before_start_wraps_past_midnight() -> None:
    window = TimeWindow(london(22), london(2))

    assert window.contains(utc(1, 5, 23, 0))
    assert window.contains(utc(1, 6, 1, 0))           # belongs to the window opened the day before
    assert not window.contains(utc(1, 5, 12, 0))
    assert not window.contains(utc(1, 6, 2, 0))


def test_equal_bounds_in_one_zone_are_a_full_day() -> None:
    window = TimeWindow(london(8), london(8))

    assert window.contains(utc(1, 5, 7, 59))
    assert window.contains(utc(1, 5, 8, 0))


def test_bounds_may_be_in_different_zones() -> None:
    window = TimeWindow(time(9, 0, tzinfo=TOKYO), london(8))     # 00:00-08:00 UTC in winter

    assert window.contains(utc(1, 5, 0, 0))
    assert window.contains(utc(1, 5, 7, 59))
    assert not window.contains(utc(1, 5, 8, 0))
    assert not window.contains(utc(1, 4, 23, 59))


def test_only_start_runs_to_midnight_in_its_zone() -> None:
    window = TimeWindow(start=london(20))

    assert window.contains(utc(1, 5, 23, 59))
    assert not window.contains(utc(1, 5, 19, 59))
    assert not window.contains(utc(1, 6, 0, 0))


def test_only_end_runs_from_midnight_in_its_zone() -> None:
    window = TimeWindow(end=london(4))

    assert window.contains(utc(1, 5, 0, 0))
    assert not window.contains(utc(1, 5, 4, 0))
    assert not window.contains(utc(1, 4, 23, 59))


def test_no_bounds_contain_everything() -> None:
    assert TimeWindow().contains(utc(1, 5, 3, 17))


def test_a_naive_instant_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeWindow(london(8), london(16)).contains(datetime(2026, 1, 5, 9, 0))
