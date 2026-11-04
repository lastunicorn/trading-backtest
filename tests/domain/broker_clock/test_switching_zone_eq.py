"""Tests for `domain.broker_clock.SwitchingZone.__eq__` and `__hash__`."""

from datetime import datetime

from domain.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ, SwitchingZone

from ._fakes import NEW_YORK


def test_same_zones_and_switch_are_equal_whatever_the_name() -> None:
    twin = SwitchingZone(HISTDATA_TZ.before, HISTDATA_TZ.after, HISTDATA_TZ.switch, "another label")

    assert twin == HISTDATA_TZ
    assert hash(twin) == hash(HISTDATA_TZ)


def test_a_different_switch_is_not_equal() -> None:
    assert SwitchingZone(HISTDATA_TZ.before, HISTDATA_TZ.after, datetime(2020, 1, 1), "x") != HISTDATA_TZ


def test_other_zones_are_not_equal() -> None:
    assert HISTDATA_TZ != NEW_YORK
    assert HISTDATA_TZ != BROKER_SERVER_TZ
