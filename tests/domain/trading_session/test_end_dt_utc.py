"""Tests for `TradingSession.end_dt_utc`."""

from datetime import UTC, datetime

from domain.trading_session import TradingSession


def test_returns_the_cached_utc_end() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    assert session.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)
