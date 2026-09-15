"""Tests for `TradingSession.add`."""

from datetime import UTC, datetime

from domain.bar import Bar
from domain.trading_session import TradingSession


def make_session() -> TradingSession:
    return TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )


def make_bar(hour: int, minute: int = 0) -> Bar:
    return Bar(
        dt=datetime(2026, 1, 15, hour, minute, tzinfo=UTC),
        open=1.1000,
        high=1.1010,
        low=1.0990,
        close=1.1005,
    )


def test_bar_inside_window_is_added_and_returns_true() -> None:
    session = make_session()
    bar = make_bar(9)

    assert session.add(bar) is True
    assert session.bar_count == 1


def test_bar_outside_window_is_not_added_and_returns_false() -> None:
    session = make_session()
    bar = make_bar(7)

    assert session.add(bar) is False
    assert session.bar_count == 0


def test_bar_at_the_exclusive_end_boundary_is_not_added() -> None:
    session = make_session()
    bar = make_bar(16, 30)

    assert session.add(bar) is False
    assert session.bar_count == 0
