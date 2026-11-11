"""Tests for `TradingSessionInstance.bar_count`."""

from datetime import UTC, datetime

from domain.bar_approach.bar import Bar
from domain.market_data.trading_session_instance import TradingSessionInstance


def test_starts_at_zero() -> None:
    session = TradingSessionInstance(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    assert session.bar_count == 0


def test_counts_each_added_bar() -> None:
    session = TradingSessionInstance(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 0, tzinfo=UTC), open=1.1, high=1.1, low=1.1, close=1.1))
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 5, tzinfo=UTC), open=1.1, high=1.1, low=1.1, close=1.1))

    assert session.bar_count == 2
