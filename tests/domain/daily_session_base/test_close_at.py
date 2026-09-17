"""Tests for `DailySessionBase.close_at`."""

from datetime import date, datetime

import pytest

from domain.bar_approach.position import Position
from tests.domain.daily_session_base._fakes import FakeDailySession


def test_first_call_closes_and_returns_true() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    at = datetime(2026, 1, 15, 12, 0)

    result = session.close_at(at)

    assert result is True
    assert session.is_closed is True
    assert session.closed_dt == at


def test_delegates_to_close_all_positions() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    position = Position(open_dt=datetime(2026, 1, 15, 9, 0), open_price=1.1000, sl=1.0990, tp=1.1020)
    session._positions.append(position)
    at = datetime(2026, 1, 15, 12, 0)

    session.close_at(at)

    assert position.is_closed is True
    assert position.close_dt == at


def test_repeated_call_with_the_same_at_is_a_no_op() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    at = datetime(2026, 1, 15, 12, 0)
    session.close_at(at)

    result = session.close_at(at)

    assert result is False


def test_repeated_call_with_a_different_at_raises() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    session.close_at(datetime(2026, 1, 15, 12, 0))

    with pytest.raises(RuntimeError):
        session.close_at(datetime(2026, 1, 15, 13, 0))
