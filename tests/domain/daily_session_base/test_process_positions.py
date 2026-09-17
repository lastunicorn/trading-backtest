"""Tests for `DailySessionBase._process_positions`."""

from datetime import date, datetime

from domain.bar_approach.position import Outcome, PendingPosition
from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar


def test_position_opened_by_this_bar_is_immediately_checked_against_it() -> None:
    """A pending position that triggers on `bar` is opened and then, in the
    same `_process_positions` call, checked against that same `bar` -- so a
    bar wide enough to both trigger entry and hit TP resolves in one step."""
    session = FakeDailySession(date(2026, 1, 15))
    pending = PendingPosition(price=1.1010, sl=1.1000, tp=1.1020)
    session._pending_positions.append(pending)
    bar = make_bar(datetime(2026, 1, 15, 9, 0), open=1.1010, high=1.1025, low=1.1005, close=1.1020)

    session._process_positions(bar)

    assert session._pending_positions == []
    assert len(session._positions) == 1
    opened = session._positions[0]
    assert opened.is_closed is True
    assert opened.outcome == Outcome.TP_HIT


def test_an_already_open_position_is_updated() -> None:
    session = FakeDailySession(date(2026, 1, 15))
    pending = PendingPosition(price=1.1010, sl=1.1000, tp=1.1030)
    session._pending_positions.append(pending)
    triggering_bar = make_bar(datetime(2026, 1, 15, 9, 0), open=1.1010, high=1.1012, low=1.1008, close=1.1010)
    session._process_positions(triggering_bar)

    sl_bar = make_bar(datetime(2026, 1, 15, 9, 5), open=1.1005, high=1.1006, low=1.0999, close=1.1000)
    session._process_positions(sl_bar)

    assert session._positions[0].outcome == Outcome.SL_HIT
