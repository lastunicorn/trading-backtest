"""Tests for `LONDON_SESSION`'s window."""

from datetime import time
from zoneinfo import ZoneInfo

from domain.trading_session_template import LONDON_SESSION

LONDON = ZoneInfo("Europe/London")


def test_window() -> None:
    assert LONDON_SESSION.start_time == time(8, 0, tzinfo=LONDON)
    assert LONDON_SESSION.end_time == time(16, 30, tzinfo=LONDON)
