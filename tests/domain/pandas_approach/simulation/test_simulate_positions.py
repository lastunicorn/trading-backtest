"""Tests for `domain.pandas_approach.simulation.simulate_positions`."""

import pandas as pd
import pytest

from domain.pandas_approach.position import PositionOutcome
from domain.pandas_approach.simulation import AmbiguityPolicy, ResolveFrom, simulate_positions

from ._fakes import QUIET, T0, at, data, long_position, short_position

HITS_TP_LONG = (1.1000, 1.1045, 1.0995, 1.1030)
HITS_SL_LONG = (1.1000, 1.1005, 1.0975, 1.0985)
HITS_BOTH = (1.1000, 1.1045, 1.0975, 1.1000)


def _one(bars, position, **kwargs):
    [result] = simulate_positions(data(*bars), [position], **kwargs)
    return result


# --- hits ---------------------------------------------------------------------

def test_long_take_profit() -> None:
    result = _one([QUIET, QUIET, HITS_TP_LONG, QUIET], long_position())

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_price == 1.1040
    assert result.close_dt == at(2)


def test_long_stop_loss() -> None:
    result = _one([QUIET, HITS_SL_LONG, QUIET], long_position())

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_price == 1.0980
    assert result.close_dt == at(1)


def test_short_take_profit_on_the_low() -> None:
    result = _one([QUIET, (1.1000, 1.1005, 1.0960, 1.0970)], short_position())

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_price == 1.0960


def test_short_stop_loss_on_the_high() -> None:
    result = _one([QUIET, (1.1000, 1.1020, 1.0995, 1.1010)], short_position())

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_price == 1.1020


def test_touching_the_level_exactly_counts_as_a_hit() -> None:
    result = _one([QUIET, (1.1000, 1.1040, 1.0990, 1.1030)], long_position())

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT


def test_first_hit_wins_over_a_later_one() -> None:
    result = _one([QUIET, HITS_SL_LONG, HITS_TP_LONG], long_position())

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_dt == at(1)


def test_gap_through_the_stop_fills_at_the_stop_level() -> None:
    gap_down = (1.0950, 1.0955, 1.0940, 1.0945)

    result = _one([QUIET, gap_down], long_position())

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_price == 1.0980


# --- where checking starts ---------------------------------------------------------

def test_next_bar_ignores_a_hit_on_the_entry_bar() -> None:
    result = _one([HITS_TP_LONG, QUIET, HITS_SL_LONG], long_position(), resolve_from=ResolveFrom.NEXT_BAR)

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_dt == at(2)


def test_entry_bar_counts_a_hit_on_the_entry_bar() -> None:
    result = _one([HITS_TP_LONG, QUIET, HITS_SL_LONG], long_position(), resolve_from=ResolveFrom.ENTRY_BAR)

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_dt == at(0)


def test_next_bar_is_the_default() -> None:
    result = _one([HITS_TP_LONG, QUIET], long_position())

    assert result.outcome == PositionOutcome.END_OF_DATA


def test_open_time_inside_a_bar_uses_that_bar_as_the_entry_bar() -> None:
    inside_bar_1 = at(1) + pd.Timedelta("2min")

    result = _one([QUIET, HITS_SL_LONG, HITS_TP_LONG], long_position(open_dt=inside_bar_1))

    # Bar 1 is the entry bar and skipped under NEXT_BAR; bar 2 decides.
    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_dt == at(2)


# --- ambiguous bars ---------------------------------------------------------------------

def test_ambiguous_bar_is_excluded_by_default() -> None:
    result = _one([QUIET, HITS_BOTH], long_position())

    assert result.outcome == PositionOutcome.AMBIGUOUS
    assert result.close_price is None
    assert result.close_dt == at(1)


def test_ambiguous_bar_assumed_stop_loss() -> None:
    result = _one([QUIET, HITS_BOTH], long_position(), ambiguity=AmbiguityPolicy.ASSUME_SL)

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT
    assert result.close_price == 1.0980


def test_ambiguous_bar_assumed_take_profit() -> None:
    result = _one([QUIET, HITS_BOTH], long_position(), ambiguity=AmbiguityPolicy.ASSUME_TP)

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_price == 1.1040


def test_ambiguity_policy_only_matters_when_both_levels_are_hit_on_one_bar() -> None:
    result = _one([QUIET, HITS_TP_LONG], long_position(), ambiguity=AmbiguityPolicy.ASSUME_SL)

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT


# --- time stop and end of data -----------------------------------------------------

def test_time_stop_closes_at_the_last_bar_before_exit_dt() -> None:
    bars = [QUIET, QUIET, (1.1000, 1.1010, 1.0990, 1.1007), HITS_TP_LONG]

    result = _one(bars, long_position(exit_dt=at(3)))

    # Bar 3 opens at exit_dt, so its TP is never reached.
    assert result.outcome == PositionOutcome.MANUAL_CLOSE
    assert result.close_price == 1.1007
    assert result.close_dt == at(3)


def test_time_stop_inside_a_bar_still_trades_that_bar() -> None:
    bars = [QUIET, QUIET, HITS_TP_LONG, QUIET]

    result = _one(bars, long_position(exit_dt=at(2) + pd.Timedelta("2min")))

    assert result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert result.close_dt == at(2)


def test_hit_before_the_time_stop_wins() -> None:
    result = _one([QUIET, HITS_SL_LONG, QUIET, QUIET], long_position(exit_dt=at(3)))

    assert result.outcome == PositionOutcome.STOP_LOSS_HIT


def test_time_stop_right_after_the_entry_bar_closes_at_the_entry_bar_close() -> None:
    result = _one([QUIET, HITS_TP_LONG], long_position(exit_dt=at(1)))

    assert result.outcome == PositionOutcome.MANUAL_CLOSE
    assert result.close_price == QUIET[3]


def test_no_hit_and_no_time_stop_closes_at_end_of_data() -> None:
    last = (1.1000, 1.1010, 1.0990, 1.1003)

    result = _one([QUIET, QUIET, last], long_position())

    assert result.outcome == PositionOutcome.END_OF_DATA
    assert result.close_price == 1.1003
    assert result.close_dt == at(2)


def test_time_stop_beyond_the_data_is_end_of_data_not_manual_close() -> None:
    result = _one([QUIET, QUIET], long_position(exit_dt=at(10)))

    assert result.outcome == PositionOutcome.END_OF_DATA
    assert result.close_dt == at(1)


def test_entry_on_the_last_bar_closes_at_end_of_data() -> None:
    result = _one([QUIET], long_position())

    assert result.outcome == PositionOutcome.END_OF_DATA
    assert result.close_dt == T0


# --- the batch ---------------------------------------------------------------------

def test_closes_every_position_in_place_and_keeps_their_order() -> None:
    first = long_position()
    second = short_position(open_dt=at(1))

    result = simulate_positions(data(QUIET, QUIET, HITS_TP_LONG), [first, second])

    assert result[0] is first and result[1] is second
    assert first.is_closed and second.is_closed


def test_positions_are_resolved_independently() -> None:
    # One bar hits the long's TP and, separately, the short's SL.
    bars = [QUIET, (1.1000, 1.1045, 1.0995, 1.1030)]

    long_result, short_result = simulate_positions(data(*bars), [long_position(), short_position()])

    assert long_result.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert short_result.outcome == PositionOutcome.STOP_LOSS_HIT


def test_no_positions_gives_an_empty_list() -> None:
    assert simulate_positions(data(QUIET), []) == []


def test_position_opening_before_the_first_bar_is_rejected() -> None:
    with pytest.raises(ValueError, match="before the first bar"):
        simulate_positions(data(QUIET), [long_position(open_dt=T0 - pd.Timedelta("5min"))])


def test_already_closed_position_is_rejected() -> None:
    position = long_position()
    position.close(at(1), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    with pytest.raises(ValueError, match="already closed"):
        simulate_positions(data(QUIET, QUIET), [position])
