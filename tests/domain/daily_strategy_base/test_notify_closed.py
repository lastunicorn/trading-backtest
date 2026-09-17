"""Tests for `DailyStrategyBase._notify_closed`."""

from datetime import date

from tests.domain.daily_strategy_base._fakes import FakeDailyStrategy
from tests.domain.daily_session_base._fakes import FakeDailySession


def test_does_nothing_when_no_callback_is_set() -> None:
    strategy = FakeDailyStrategy()
    session = FakeDailySession(date(2026, 1, 15))

    strategy._notify_closed(session)  # must not raise


def test_calls_the_configured_callback_with_the_session() -> None:
    received = []
    strategy = FakeDailyStrategy(on_session_closed=received.append)
    session = FakeDailySession(date(2026, 1, 15))

    strategy._notify_closed(session)

    assert received == [session]
