"""Tests for `domain.broker_clock.ShiftedZone.utcoffset`."""

from datetime import timedelta

from domain.broker_clock import BROKER_SERVER_TZ

from ._fakes import MISMATCH, SUMMER, WINTER


def test_gmt_plus_2_in_us_winter() -> None:
    assert BROKER_SERVER_TZ.utcoffset(WINTER) == timedelta(hours=2)


def test_gmt_plus_3_in_us_summer() -> None:
    assert BROKER_SERVER_TZ.utcoffset(SUMMER) == timedelta(hours=3)


def test_follows_the_us_switch_date_not_the_eu_one() -> None:
    # Europe/Athens would still be GMT+2 here.
    assert BROKER_SERVER_TZ.utcoffset(MISMATCH) == timedelta(hours=3)


def test_switches_seven_hours_after_new_york_does() -> None:
    # New York springs forward at 02:00 on 2020-03-08 -> 09:00 on the server.
    before = MISMATCH.replace(day=8, hour=8, minute=59)
    after = MISMATCH.replace(day=8, hour=10, minute=0)

    assert BROKER_SERVER_TZ.utcoffset(before) == timedelta(hours=2)
    assert BROKER_SERVER_TZ.utcoffset(after) == timedelta(hours=3)


def test_none_gives_none() -> None:
    assert BROKER_SERVER_TZ.utcoffset(None) is None
