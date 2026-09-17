"""Tests for `TradingSession.bar_count`."""

from datetime import UTC, datetime

from domain.bar_approach.bar import Bar
from domain.trading_session import TradingSession


def test_starts_at_zero() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    assert session.bar_count == 0


def test_counts_each_added_bar() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 0, tzinfo=UTC), open=1.1, high=1.1, low=1.1, close=1.1))
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 5, tzinfo=UTC), open=1.1, high=1.1, low=1.1, close=1.1))

    assert session.bar_count == 2
