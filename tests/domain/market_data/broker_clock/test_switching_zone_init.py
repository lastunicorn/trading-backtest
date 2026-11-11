"""Tests for `domain.market_data.broker_clock.SwitchingZone.__init__`."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from domain.market_data.broker_clock import ShiftedZone, SwitchingZone

from ._fakes import NEW_YORK


def test_zones_agreeing_at_the_switch_are_accepted() -> None:
    london_minus_5 = ShiftedZone(ZoneInfo("Europe/London"), timedelta(hours=-5), "x")

    zone = SwitchingZone(NEW_YORK, london_minus_5, datetime(2019, 1, 1), "name")

    assert (zone.before, zone.after, zone.switch, zone.name) == (NEW_YORK, london_minus_5, datetime(2019, 1, 1), "name")


def test_zones_disagreeing_at_the_switch_raise() -> None:
    # In March 2019's mismatch week New York is UTC-4 and London - 5h is UTC-5.
    london_minus_5 = ShiftedZone(ZoneInfo("Europe/London"), timedelta(hours=-5), "x")

    with pytest.raises(ValueError, match="different UTC offsets"):
        SwitchingZone(NEW_YORK, london_minus_5, datetime(2019, 3, 20), "name")
