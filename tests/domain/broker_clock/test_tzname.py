"""Tests for `domain.broker_clock.ShiftedZone.tzname`."""

from domain.broker_clock import BROKER_SERVER_TZ

from ._fakes import WINTER


def test_is_the_zone_name_all_year() -> None:
    assert BROKER_SERVER_TZ.tzname(WINTER) == "broker-server (America/New_York+7h)"
    assert BROKER_SERVER_TZ.tzname(None) == "broker-server (America/New_York+7h)"
