"""Tests for `DailyStrategyBase.add_bar`."""

from datetime import date, datetime

from tests.domain.daily_strategy_base._fakes import FakeDailyStrategy, make_bar


def test_first_bar_of_a_new_day_creates_its_session() -> None:
    strategy = FakeDailyStrategy()
    bar = make_bar(datetime(2026, 1, 15, 9, 0))

    strategy.add_bar(bar)

    assert date(2026, 1, 15) in strategy._sessions
    session = strategy._sessions[date(2026, 1, 15)]
    assert session.processed_bars == [bar]


def test_second_bar_of_the_same_day_reuses_the_existing_session() -> None:
    strategy = FakeDailyStrategy()
    first = make_bar(datetime(2026, 1, 15, 9, 0))
    second = make_bar(datetime(2026, 1, 15, 9, 5))

    strategy.add_bar(first)
    strategy.add_bar(second)

    assert len(strategy._sessions) == 1
    session = strategy._sessions[date(2026, 1, 15)]
    assert session.processed_bars == [first, second]


def test_a_bar_crossing_into_a_new_day_force_closes_the_previous_days_session() -> None:
    """`FakeDailySession` spans exactly one calendar day, so the first bar of
    day 2 lands exactly on day 1's session's own `end_dt`, forcing it closed
    -- the scenario `add_bar`'s docstring describes as noticing a session
    force-close itself and dropping it from the live list."""
    closed_sessions = []
    strategy = FakeDailyStrategy(on_session_closed=closed_sessions.append)

    strategy.add_bar(make_bar(datetime(2026, 1, 15, 9, 0)))
    strategy.add_bar(make_bar(datetime(2026, 1, 16, 0, 0)))

    day_one_session = strategy._sessions[date(2026, 1, 15)]
    assert day_one_session.is_closed is True
    assert day_one_session not in strategy._live_sessions
    assert closed_sessions == [day_one_session]


def test_still_live_earlier_session_also_receives_a_new_days_bar() -> None:
    """A session with `span_days=2` is still live when the next calendar
    day's first bar arrives, so both the new day's session and the
    still-resolving earlier one are fed that same bar."""
    strategy = FakeDailyStrategy(span_days=2)
    day_one_bar = make_bar(datetime(2026, 1, 15, 9, 0))
    day_two_bar = make_bar(datetime(2026, 1, 16, 9, 0))

    strategy.add_bar(day_one_bar)
    strategy.add_bar(day_two_bar)

    day_one_session = strategy._sessions[date(2026, 1, 15)]
    day_two_session = strategy._sessions[date(2026, 1, 16)]
    assert day_one_session.processed_bars == [day_one_bar, day_two_bar]
    assert day_two_session.processed_bars == [day_two_bar]
    assert day_one_session in strategy._live_sessions
