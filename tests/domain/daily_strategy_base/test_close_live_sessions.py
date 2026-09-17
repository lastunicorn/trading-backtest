"""Tests for `DailyStrategyBase.close_live_sessions`."""

from datetime import datetime

from tests.domain.daily_strategy_base._fakes import FakeDailyStrategy, make_bar


def test_no_op_when_nothing_is_live() -> None:
    strategy = FakeDailyStrategy()
    strategy.close_live_sessions()
    assert strategy._live_sessions == []


def test_force_closes_every_live_session_at_its_own_end_dt() -> None:
    closed_sessions = []
    strategy = FakeDailyStrategy(on_session_closed=closed_sessions.append)
    strategy.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
    session = strategy._sessions[strategy._session_order[0]]

    strategy.close_live_sessions()

    assert session.is_closed is True
    assert session.closed_dt == session.end_dt
    assert closed_sessions == [session]
    assert strategy._live_sessions == []


def test_multiple_still_live_sessions_are_all_closed_and_notified() -> None:
    closed_sessions = []
    strategy = FakeDailyStrategy(span_days=2, on_session_closed=closed_sessions.append)
    strategy.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
    strategy.add_bar(make_bar(datetime(2026, 1, 16, 9, 0)))

    strategy.close_live_sessions()

    assert len(closed_sessions) == 2
    assert all(session.is_closed for session in closed_sessions)
    assert strategy._live_sessions == []
