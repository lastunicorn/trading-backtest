"""Tests for `TOKYO_SESSION`'s window."""

from datetime import date, time
from zoneinfo import ZoneInfo

from domain.trading_session_template import TOKYO_SESSION

TOKYO = ZoneInfo("Asia/Tokyo")

# Dates safely inside (not near the edges of) a DST period, so the exact
# transition day doesn't matter -- only that one is winter and one is summer.
WINTER_DATE = date(2026, 1, 15)
SUMMER_DATE = date(2026, 7, 15)


def test_window() -> None:
    assert TOKYO_SESSION.start_time == time(9, 0, tzinfo=TOKYO)
    assert TOKYO_SESSION.end_time == time(15, 30, tzinfo=TOKYO)


def test_no_dst_so_utc_offset_is_constant() -> None:
    winter_start = TOKYO_SESSION.start_time_utc_on(WINTER_DATE)
    summer_start = TOKYO_SESSION.start_time_utc_on(SUMMER_DATE)

    assert winter_start.timetz() == summer_start.timetz()
