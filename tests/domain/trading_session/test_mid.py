"""Tests for `TradingSession.mid`."""

from datetime import UTC, datetime

from domain.bar_approach.bar import Bar
from domain.trading_session import TradingSession


def test_delegates_to_the_bar_block_midpoint() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 0, tzinfo=UTC), open=1.1000, high=1.1010, low=1.0990, close=1.1005))
    session.add(Bar(dt=datetime(2026, 1, 15, 9, 5, tzinfo=UTC), open=1.1005, high=1.1030, low=1.1000, close=1.1020))

    assert session.mid == session.bar_block.mid
    assert session.mid == (1.1030 + 1.0990) / 2
