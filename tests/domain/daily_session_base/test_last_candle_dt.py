"""Tests for `DailySessionBase.last_candle_dt`."""

from datetime import date, datetime

from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def test_none_before_any_bar() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    assert session.last_candle_dt is None


def test_advances_with_each_later_bar() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    second_dt = datetime(2026, 1, 15, 9, 5)

    session.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
    session.add_bar(make_bar(second_dt))

    assert session.last_candle_dt == second_dt


def test_unchanged_by_a_bar_that_does_not_advance_past_it() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    latest_dt = datetime(2026, 1, 15, 9, 5)

    session.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
    session.add_bar(make_bar(latest_dt))
    session.add_bar(make_bar(latest_dt))

    assert session.last_candle_dt == latest_dt
