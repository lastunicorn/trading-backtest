"""Tests for `DailySessionBase.is_closed`."""

from datetime import date, datetime

from tests.domain.daily_session_base._fakes import FakeDailySession


def test_false_before_any_close() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    assert session.is_closed is False


def test_true_after_close_at() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    session.close_at(datetime(2026, 1, 15, 12, 0))
    assert session.is_closed is True
