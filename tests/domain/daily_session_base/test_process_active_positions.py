"""Tests for `DailySessionBase._process_active_positions`."""

from datetime import date, datetime

from domain.bar_approach.position import Outcome, Position
from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def test_position_not_hit_stays_open() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    position = Position(open_dt=datetime(2026, 1, 15, 9, 0), open_price=1.1010, sl=1.1000, tp=1.1030)
    session._positions.append(position)
    bar = make_bar(datetime(2026, 1, 15, 9, 5), open=1.1010, high=1.1015, low=1.1005, close=1.1010)

    session._process_active_positions(bar)

    assert position.is_closed is False
    assert position.outcome == Outcome.NONE


def test_position_hit_gets_closed() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    position = Position(open_dt=datetime(2026, 1, 15, 9, 0), open_price=1.1010, sl=1.1000, tp=1.1030)
    session._positions.append(position)
    bar = make_bar(datetime(2026, 1, 15, 9, 5), open=1.1029, high=1.1031, low=1.1025, close=1.1030)

    session._process_active_positions(bar)

    assert position.is_closed is True
    assert position.outcome == Outcome.TP_HIT


def test_already_closed_position_is_left_untouched() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    position = Position(open_dt=datetime(2026, 1, 15, 9, 0), open_price=1.1010, sl=1.1000, tp=1.1030)
    position.close_by_tp(datetime(2026, 1, 15, 9, 5))
    session._positions.append(position)
    sl_hitting_bar = make_bar(datetime(2026, 1, 15, 9, 10), open=1.0999, high=1.1000, low=1.0990, close=1.0995)

    session._process_active_positions(sl_hitting_bar)

    assert position.outcome == Outcome.TP_HIT
