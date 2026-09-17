"""Tests for `DailySessionBase.close_at_session_end`."""

from datetime import date, datetime

from tests.domain.daily_session_base._fakes import FakeDailySession


def test_closes_at_end_dt_and_returns_true() -> None:
    session = FakeDailySession(date(2026, 1, 15))

    result = session.close_at_session_end()

    assert result is True
    assert session.is_closed is True
    assert session.closed_dt == session.end_dt


def test_second_call_is_a_no_op_and_returns_false() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    session.close_at_session_end()

    result = session.close_at_session_end()

    assert result is False
    assert session.closed_dt == session.end_dt
