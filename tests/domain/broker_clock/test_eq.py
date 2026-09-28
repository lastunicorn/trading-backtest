"""Tests for `domain.broker_clock.ShiftedZone.__eq__` and `__hash__`."""

from datetime import timedelta
from zoneinfo import ZoneInfo

from domain.broker_clock import BROKER_SERVER_TZ, ShiftedZone


def test_same_base_and_shift_are_equal_whatever_the_name() -> None:
    twin = ShiftedZone(ZoneInfo("America/New_York"), timedelta(hours=7), "another label")

    assert twin == BROKER_SERVER_TZ
    assert hash(twin) == hash(BROKER_SERVER_TZ)


def test_different_shift_or_base_is_not_equal() -> None:
    assert ShiftedZone(ZoneInfo("America/New_York"), timedelta(hours=6), "x") != BROKER_SERVER_TZ
    assert ShiftedZone(ZoneInfo("Europe/London"), timedelta(hours=7), "x") != BROKER_SERVER_TZ


def test_is_not_equal_to_its_base_zone() -> None:
    assert BROKER_SERVER_TZ != ZoneInfo("America/New_York")
    assert ZoneInfo("America/New_York") != BROKER_SERVER_TZ
