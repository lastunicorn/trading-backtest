"""Tests for `domain.broker_clock.ShiftedZone.dst`."""

from datetime import timedelta

from domain.broker_clock import BROKER_SERVER_TZ

from ._fakes import MISMATCH, SUMMER, WINTER


def test_no_dst_in_us_winter() -> None:
    assert BROKER_SERVER_TZ.dst(WINTER) == timedelta(0)


def test_one_hour_dst_in_us_summer_and_mismatch_weeks() -> None:
    assert BROKER_SERVER_TZ.dst(SUMMER) == timedelta(hours=1)
    assert BROKER_SERVER_TZ.dst(MISMATCH) == timedelta(hours=1)


def test_none_gives_none() -> None:
    assert BROKER_SERVER_TZ.dst(None) is None
