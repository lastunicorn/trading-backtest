"""Tests for `DailySessionBase.add_bar`."""

from datetime import date, datetime

import pytest

from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def make_session() -> FakeDailySession:
    session = FakeDailySession(date(2026, 1, 15))
    session.start_dt = datetime(2026, 1, 15, 8, 0)
    session.end_dt = datetime(2026, 1, 15, 16, 0)
    return session


def test_bar_before_start_dt_is_rejected() -> None:
    session = make_session()
    bar = make_bar(datetime(2026, 1, 15, 7, 59))

    assert session.add_bar(bar) is False
    assert session.processed_bars == []
    assert session.is_closed is False


def test_bar_inside_the_window_is_processed_and_accepted() -> None:
    session = make_session()
    bar = make_bar(datetime(2026, 1, 15, 9, 0))

    assert session.add_bar(bar) is True
    assert session.processed_bars == [bar]


def test_bar_at_end_dt_force_closes_the_session_and_is_rejected() -> None:
    session = make_session()
    bar = make_bar(datetime(2026, 1, 15, 16, 0))

    assert session.add_bar(bar) is False
    assert session.processed_bars == []
    assert session.is_closed is True
    assert session.closed_dt == session.end_dt


def test_bar_past_end_dt_also_force_closes_the_session() -> None:
    session = make_session()
    bar = make_bar(datetime(2026, 1, 15, 18, 0))

    assert session.add_bar(bar) is False
    assert session.is_closed is True
    assert session.closed_dt == session.end_dt


def test_bar_not_advancing_past_the_last_seen_candle_is_rejected() -> None:
    session = make_session()
    first = make_bar(datetime(2026, 1, 15, 9, 5))
    repeat = make_bar(datetime(2026, 1, 15, 9, 5))

    session.add_bar(first)
    result = session.add_bar(repeat)

    assert result is False
    assert session.processed_bars == [first]


def test_add_bar_after_close_raises() -> None:
    session = make_session()
    session.close_at(session.end_dt)

    with pytest.raises(RuntimeError):
        session.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
