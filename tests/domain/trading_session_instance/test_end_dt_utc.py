"""Tests for `TradingSessionInstance.end_dt_utc`."""

from datetime import UTC, datetime

from domain.trading_session_instance import TradingSessionInstance


def test_returns_the_cached_utc_end() -> None:
    session = TradingSessionInstance(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )
    assert session.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)
