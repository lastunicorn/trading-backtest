"""Tests for `DailySessionBase.first_candle_dt`."""

from datetime import date, datetime

from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def test_none_before_any_bar() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    assert session.first_candle_dt is None


def test_set_to_the_first_bar_added() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    first_dt = datetime(2026, 1, 15, 9, 0)

    session.add_bar(make_bar(first_dt))

    assert session.first_candle_dt == first_dt


def test_stays_at_the_first_bar_once_later_bars_arrive() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    first_dt = datetime(2026, 1, 15, 9, 0)

    session.add_bar(make_bar(first_dt))
    session.add_bar(make_bar(datetime(2026, 1, 15, 9, 5)))

    assert session.first_candle_dt == first_dt
