"""Tests for `TradingSessionTemplate.end_time_utc_on`."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from domain.trading_session_template import TradingSessionTemplate

LONDON = ZoneInfo("Europe/London")

# Dates safely inside (not near the edges of) a DST period, so the exact
# transition day doesn't matter -- only that one is winter and one is summer.
WINTER_DATE = date(2026, 1, 15)
SUMMER_DATE = date(2026, 7, 15)


def test_under_gmt() -> None:
    template = TradingSessionTemplate(
        start_time=time(8, 0, tzinfo=LONDON),
        end_time=time(16, 30, tzinfo=LONDON),
    )
    assert template.end_time_utc_on(WINTER_DATE) == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)


def test_under_bst() -> None:
    template = TradingSessionTemplate(
        start_time=time(8, 0, tzinfo=LONDON),
        end_time=time(16, 30, tzinfo=LONDON),
    )
    # BST is UTC+1, so the same local clock time is an hour earlier in UTC.
    assert template.end_time_utc_on(SUMMER_DATE) == datetime(2026, 7, 15, 15, 30, tzinfo=UTC)
