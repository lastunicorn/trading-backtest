"""Tests for `TradingSession.create_session`."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from domain.market_data.trading_session import LONDON_SESSION, TradingSession

TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
WINTER_DATE = date(2026, 1, 15)


def test_non_wrapping_session_keeps_the_same_calendar_date() -> None:
    instance = LONDON_SESSION.create_session(WINTER_DATE)

    assert instance.start_dt_utc() == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert instance.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)


def test_session_crossing_midnight_rolls_end_to_the_next_day() -> None:
    # Same tz on both ends keeps the arithmetic obvious: 23:00 -> 01:00 UTC
    # can only make sense as a 2-hour window into the next day.
    session = TradingSession(
        start_time=time(23, 0, tzinfo=UTC),
        end_time=time(1, 0, tzinfo=UTC),
    )
    instance = session.create_session(WINTER_DATE)

    assert instance.start_dt_utc() == datetime(2026, 1, 15, 23, 0, tzinfo=UTC)
    assert instance.end_dt_utc() == datetime(2026, 1, 16, 1, 0, tzinfo=UTC)


def test_session_with_different_start_and_end_zones() -> None:
    # Asia start paired with a London end, per the module docstring -- the
    # wrap decision has to compare UTC instants, since "09:00" and "16:30" as
    # bare local times carry no meaningful order across zones.
    session = TradingSession(
        start_time=time(9, 0, tzinfo=TOKYO),
        end_time=time(16, 30, tzinfo=LONDON),
    )
    instance = session.create_session(WINTER_DATE)

    assert instance.start_dt_utc() == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
    assert instance.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)
