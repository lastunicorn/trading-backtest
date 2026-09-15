"""Tests for `LondonSessionTemplate`'s frozen defaults."""

from datetime import time
from zoneinfo import ZoneInfo

from domain.trading_session_template import LondonSessionTemplate

LONDON = ZoneInfo("Europe/London")


def test_defaults() -> None:
    template = LondonSessionTemplate()
    assert template.start_time == time(8, 0, tzinfo=LONDON)
    assert template.end_time == time(16, 30, tzinfo=LONDON)
