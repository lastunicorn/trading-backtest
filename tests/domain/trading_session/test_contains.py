"""Tests for `TradingSession.contains`."""

from datetime import UTC, datetime, timedelta, timezone

from domain.trading_session import TradingSession

LONDON_PLUS_1 = timezone(timedelta(hours=1))


def make_session() -> TradingSession:
    return TradingSession(
        start_dt=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_dt=datetime(2026, 1, 15, 16, 30, tzinfo=UTC),
    )


def test_start_is_inclusive() -> None:
    session = make_session()
    assert session.contains(datetime(2026, 1, 15, 8, 0, tzinfo=UTC))


def test_end_is_exclusive() -> None:
    session = make_session()
    assert not session.contains(datetime(2026, 1, 15, 16, 30, tzinfo=UTC))


def test_dt_inside_window_is_contained() -> None:
    session = make_session()
    assert session.contains(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))


def test_dt_outside_window_is_not_contained() -> None:
    session = make_session()
    assert not session.contains(datetime(2026, 1, 15, 7, 59, tzinfo=UTC))
    assert not session.contains(datetime(2026, 1, 15, 16, 31, tzinfo=UTC))


def test_naive_dt_is_assumed_to_already_be_in_the_session_clock() -> None:
    session = make_session()
    assert session.contains(datetime(2026, 1, 15, 12, 0))


def test_aware_dt_in_another_zone_is_converted_before_comparing() -> None:
    session = make_session()
    # 09:00 UTC+1 is 08:00 UTC -- the session's own start instant.
    assert session.contains(datetime(2026, 1, 15, 9, 0, tzinfo=LONDON_PLUS_1))
