"""Tests for `TradingSession.bars`."""

from datetime import UTC, datetime

from domain.bar_approach.bar import Bar
from domain.bar_approach.bar_block import BarBlock
from domain.trading_session import TradingSession


def test_exposes_the_underlying_bar_block() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    bar = Bar(
        dt=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        open=1.1000,
        high=1.1010,
        low=1.0990,
        close=1.1005,
    )
    session.add(bar)

    assert isinstance(session.bar_block, BarBlock)
    assert session.bar_block.open_value == 1.1000
    assert session.bar_block.close_value == 1.1005
