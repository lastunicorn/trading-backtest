"""Tests for `TradingSessionTemplate.start_time_on`."""

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from domain.trading_session_template import TradingSessionTemplate

LONDON = ZoneInfo("Europe/London")
WINTER_DATE = date(2026, 1, 15)


def test_combines_date_and_local_time() -> None:
    template = TradingSessionTemplate(
        start_time=time(8, 0, tzinfo=LONDON),
        end_time=time(16, 30, tzinfo=LONDON),
    )
    assert template.start_time_on(WINTER_DATE) == datetime(2026, 1, 15, 8, 0, tzinfo=LONDON)
