"""Tests for `AsianSessionTemplate`'s frozen defaults."""

from datetime import date, time
from zoneinfo import ZoneInfo

from domain.trading_session_template import AsianSessionTemplate

TOKYO = ZoneInfo("Asia/Tokyo")

# Dates safely inside (not near the edges of) a DST period, so the exact
# transition day doesn't matter -- only that one is winter and one is summer.
WINTER_DATE = date(2026, 1, 15)
SUMMER_DATE = date(2026, 7, 15)


def test_defaults() -> None:
    template = AsianSessionTemplate()
    assert template.start_time == time(9, 0, tzinfo=TOKYO)
    assert template.end_time == time(18, 0, tzinfo=TOKYO)


def test_no_dst_so_utc_offset_is_constant() -> None:
    template = AsianSessionTemplate()
    winter_start = template.start_time_utc_on(WINTER_DATE)
    summer_start = template.start_time_utc_on(SUMMER_DATE)

    assert winter_start.timetz() == summer_start.timetz()
