"""Tests for `domain.broker_clock.SwitchingZone.__str__` and `tzname`."""

from datetime import datetime

from domain.broker_clock import HISTDATA_TZ


def test_str_and_tzname_are_the_name() -> None:
    assert str(HISTDATA_TZ) == "histdata (America/New_York, from 2019 Europe/London-5h)"
    assert HISTDATA_TZ.tzname(datetime(2018, 1, 1)) == HISTDATA_TZ.tzname(None) == str(HISTDATA_TZ)
