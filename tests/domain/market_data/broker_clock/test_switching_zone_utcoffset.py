"""Tests for `domain.market_data.broker_clock.SwitchingZone.utcoffset`, on `HISTDATA_TZ`."""

from datetime import datetime, timedelta

from domain.market_data.broker_clock import HISTDATA_TZ

# Weeks where the US is already on summer time and the EU is not yet.
MISMATCH_2018 = datetime(2018, 3, 19, 0, 0)
MISMATCH_2019 = datetime(2019, 3, 18, 0, 0)


def test_before_2019_it_follows_the_us_switch_dates() -> None:
    assert HISTDATA_TZ.utcoffset(MISMATCH_2018) == timedelta(hours=-4)
    assert HISTDATA_TZ.utcoffset(datetime(2018, 10, 29, 0, 0)) == timedelta(hours=-4)


def test_from_2019_it_follows_the_eu_switch_dates() -> None:
    assert HISTDATA_TZ.utcoffset(MISMATCH_2019) == timedelta(hours=-5)
    assert HISTDATA_TZ.utcoffset(datetime(2026, 10, 26, 0, 0)) == timedelta(hours=-5)


def test_winter_and_summer_are_new_york_offsets_in_both_eras() -> None:
    for year in (2018, 2019):
        assert HISTDATA_TZ.utcoffset(datetime(year, 1, 15)) == timedelta(hours=-5)
        assert HISTDATA_TZ.utcoffset(datetime(year, 7, 15)) == timedelta(hours=-4)


def test_none_gives_none() -> None:
    assert HISTDATA_TZ.utcoffset(None) is None
