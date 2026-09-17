"""Tests for `DailySessionBase._process_pending_positions`."""

from datetime import date, datetime

from domain.position import PendingPosition
from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def test_untriggered_pending_position_stays_pending() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    pending = PendingPosition(price=1.1050, sl=1.1040, tp=1.1070)
    session._pending_positions.append(pending)
    bar = make_bar(datetime(2026, 1, 15, 9, 0), open=1.1000, high=1.1010, low=1.0990, close=1.1005)

    session._process_pending_positions(bar)

    assert session._pending_positions == [pending]
    assert session._positions == []


def test_triggered_pending_position_moves_to_positions() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    pending = PendingPosition(price=1.1010, sl=1.1000, tp=1.1030)
    session._pending_positions.append(pending)
    bar = make_bar(datetime(2026, 1, 15, 9, 0), open=1.1005, high=1.1012, low=1.1000, close=1.1010)

    session._process_pending_positions(bar)

    assert session._pending_positions == []
    assert len(session._positions) == 1
    assert session._positions[0].open_price == pending.price


def test_every_pending_position_triggered_by_the_same_bar_is_opened() -> None:
    """Regression coverage for the same-bar-drop bug the docstring calls
    out: iterating a snapshot of `_pending_positions`, not the live list
    being mutated, so a second (or third) trigger on one bar isn't silently
    skipped once the first trigger's removal shifts the list."""
    session = FakeDailySession(date(2026, 1, 15))
    first = PendingPosition(price=1.1010, sl=1.1000, tp=1.1030)
    second = PendingPosition(price=1.1005, sl=1.0995, tp=1.1025)
    session._pending_positions.extend([first, second])
    bar = make_bar(datetime(2026, 1, 15, 9, 0), open=1.1008, high=1.1015, low=1.1003, close=1.1010)

    session._process_pending_positions(bar)

    assert session._pending_positions == []
    assert {p.open_price for p in session._positions} == {first.price, second.price}
