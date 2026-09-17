"""Tests for `DailySessionBase.closed_dt`."""

from datetime import date, datetime

from tests.domain.daily_session_base._fakes import FakeDailySession


def test_none_before_any_close() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    assert session.closed_dt is None


def test_set_to_the_close_at_argument() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    closed_at = datetime(2026, 1, 15, 12, 0)

    session.close_at(closed_at)

    assert session.closed_dt == closed_at
