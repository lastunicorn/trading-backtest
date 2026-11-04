"""Tests for `domain.broker_clock.SwitchingZone.dst`, on `HISTDATA_TZ`."""

from datetime import datetime, timedelta

from domain.broker_clock import HISTDATA_TZ


def test_follows_the_zone_in_force() -> None:
    assert HISTDATA_TZ.dst(datetime(2018, 3, 19)) == timedelta(hours=1)   # New York already on summer time
    assert HISTDATA_TZ.dst(datetime(2019, 3, 18)) == timedelta(0)         # London not yet


def test_none_gives_none() -> None:
    assert HISTDATA_TZ.dst(None) is None
