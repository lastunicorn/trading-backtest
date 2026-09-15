"""Tests for `TradingSession.__post_init__`."""

from datetime import UTC, datetime, timedelta, timezone

from domain.trading_session import TradingSession

LONDON_PLUS_1 = timezone(timedelta(hours=1))


def test_naive_bounds_are_assumed_utc() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0),
        end_dt=datetime(2026, 1, 15, 16, 30),
    )
    assert session.start_dt_utc() == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert session.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)


def test_aware_bounds_are_converted_to_utc() -> None:
    session = TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=LONDON_PLUS_1),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=LONDON_PLUS_1),
    )
    assert session.start_dt_utc() == datetime(2026, 1, 15, 7, 0, tzinfo=UTC)
    assert session.end_dt_utc() == datetime(2026, 1, 15, 15, 30, tzinfo=UTC)
