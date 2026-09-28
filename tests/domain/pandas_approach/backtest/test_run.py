"""Tests for `domain.pandas_approach.backtest.Backtest.run`."""

import math

import pandas as pd
import pytest

from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, PositionResolveDelay
from domain.pandas_approach.cost_model import FixedCost
from domain.pandas_approach.position import FRAME_COLUMNS, PositionOutcome
from domain.pandas_approach.trade_results import RESULT_COLUMNS

from ._fakes import QUIET, T0, Replay, ScriptedStrategy, at, bars, data, day, long_position, short_position


def test_every_position_comes_back_closed_with_pnl_and_split() -> None:
    result = Backtest(ScriptedStrategy([0, 1]), data(10, {0: "win", 1: "loss"})).run()

    trades = result.trades
    assert list(trades.columns) == [*FRAME_COLUMNS, *RESULT_COLUMNS, "split"]
    assert trades["outcome"].tolist() == ["take-profit-hit", "stop-loss-hit"]
    assert trades["net_pips"].tolist() == pytest.approx([18.3, -21.7])
    assert trades["split"].tolist() == ["discovery", "discovery"]


def test_trades_are_sorted_by_open_time() -> None:
    result = Backtest(ScriptedStrategy([3, 0, 1]), data(10, {})).run()

    assert result.trades["open_dt"].is_monotonic_increasing
    assert result.trades.index.tolist() == [0, 1, 2]


def test_statistics_cover_all_trades_and_each_split() -> None:
    # 10 days: 0-5 discovery, 6-7 validation, 8-9 test.
    result = Backtest(ScriptedStrategy([0, 6, 8, 9]), data(10, {0: "win", 6: "win", 8: "loss", 9: "win"})).run()

    stats = result.statistics
    assert stats.index.tolist() == ["all", "discovery", "validation", "test"]
    assert stats.loc["all", "trades"] == 4
    assert stats.loc["discovery", "wins"] == 1
    assert stats.loc["validation", "wins"] == 1
    assert stats.loc["test", "losses"] == 1


def test_cost_model_is_applied() -> None:
    result = Backtest(ScriptedStrategy([0]), data(10, {0: "win"}), cost_model=FixedCost(pips=0.5)).run()

    assert result.trades["net_pips"].tolist() == pytest.approx([19.5])


def test_ambiguity_policy_is_passed_through() -> None:
    both = data(10, {})
    # Make day 0's 10:05 bar touch both levels.
    both.data.loc[1, ["high", "low"]] = [1.1025, 1.0975]

    excluded = Backtest(ScriptedStrategy([0]), both).run()
    assumed = Backtest(ScriptedStrategy([0]), both, ambiguity_policy=AmbiguityPolicy.ASSUME_SL).run()

    assert excluded.trades["outcome"].tolist() == ["ambiguous"]
    assert assumed.trades["outcome"].tolist() == ["stop-loss-hit"]


def test_position_resolve_delay_is_passed_through() -> None:
    entry_bar_hits_tp = data(10, {})
    entry_bar_hits_tp.data.loc[0, "high"] = 1.1025

    next_bar = Backtest(ScriptedStrategy([0]), entry_bar_hits_tp).run()
    entry_bar = Backtest(ScriptedStrategy([0]), entry_bar_hits_tp, position_resolve_delay=PositionResolveDelay.ENTRY_BAR).run()

    assert next_bar.trades["outcome"].tolist() == ["end-of-data"]
    assert entry_bar.trades["outcome"].tolist() == ["take-profit-hit"]


def test_without_splits_there_is_no_split_column_and_only_all() -> None:
    result = Backtest(ScriptedStrategy([0]), data(10, {}), splits=False).run()

    assert "split" not in result.trades.columns
    assert result.statistics.index.tolist() == ["all"]


def test_split_is_cut_over_the_strategy_split_days() -> None:
    # Only days 0-4 count: 0-2 discovery, 3 validation, 4 test.
    strategy = ScriptedStrategy([3, 4], only_split_over=[day(i).date() for i in range(5)])

    result = Backtest(strategy, data(10, {})).run()

    assert result.trades["split"].tolist() == ["validation", "test"]


def test_no_positions_gives_empty_trades_and_zero_counts() -> None:
    result = Backtest(ScriptedStrategy([]), data(10, {})).run()

    assert result.trades.empty
    assert result.statistics.loc["all", "trades"] == 0


# --- exit rules -------------------------------------------------------------------
# One or two positions over a few hand-written bars; each test reads how the
# position closed from the trades frame `run()` returns.

HITS_TP_LONG = (1.1000, 1.1045, 1.0995, 1.1030)
HITS_SL_LONG = (1.1000, 1.1005, 1.0975, 1.0985)
HITS_BOTH = (1.1000, 1.1045, 1.0975, 1.1000)


def _trades(rows, *positions, **settings) -> pd.DataFrame:
    return Backtest(Replay(*positions), bars(*rows), splits=False, **settings).run().trades


def _one(rows, position, **settings) -> tuple:
    [trade] = _trades(rows, position, **settings).itertuples(index=False)
    return trade


# hits

def test_long_take_profit() -> None:
    trade = _one([QUIET, QUIET, HITS_TP_LONG, QUIET], long_position())

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_price == 1.1040
    assert trade.close_dt == at(2)


def test_long_stop_loss() -> None:
    trade = _one([QUIET, HITS_SL_LONG, QUIET], long_position())

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_price == 1.0980
    assert trade.close_dt == at(1)


def test_short_take_profit_on_the_low() -> None:
    trade = _one([QUIET, (1.1000, 1.1005, 1.0960, 1.0970)], short_position())

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_price == 1.0960


def test_short_stop_loss_on_the_high() -> None:
    trade = _one([QUIET, (1.1000, 1.1020, 1.0995, 1.1010)], short_position())

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_price == 1.1020


def test_touching_the_level_exactly_counts_as_a_hit() -> None:
    trade = _one([QUIET, (1.1000, 1.1040, 1.0990, 1.1030)], long_position())

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value


def test_first_hit_wins_over_a_later_one() -> None:
    trade = _one([QUIET, HITS_SL_LONG, HITS_TP_LONG], long_position())

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_dt == at(1)


def test_gap_through_the_stop_fills_at_the_stop_level() -> None:
    gap_down = (1.0950, 1.0955, 1.0940, 1.0945)

    trade = _one([QUIET, gap_down], long_position())

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_price == 1.0980


# where checking starts

def test_next_bar_ignores_a_hit_on_the_entry_bar() -> None:
    trade = _one([HITS_TP_LONG, QUIET, HITS_SL_LONG], long_position(), position_resolve_delay=PositionResolveDelay.NEXT_BAR)

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_dt == at(2)


def test_entry_bar_counts_a_hit_on_the_entry_bar() -> None:
    trade = _one([HITS_TP_LONG, QUIET, HITS_SL_LONG], long_position(), position_resolve_delay=PositionResolveDelay.ENTRY_BAR)

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_dt == at(0)


def test_next_bar_is_the_default() -> None:
    trade = _one([HITS_TP_LONG, QUIET], long_position())

    assert trade.outcome == PositionOutcome.END_OF_DATA.value


def test_open_time_inside_a_bar_uses_that_bar_as_the_entry_bar() -> None:
    inside_bar_1 = at(1) + pd.Timedelta("2min")

    trade = _one([QUIET, HITS_SL_LONG, HITS_TP_LONG], long_position(open_dt=inside_bar_1))

    # Bar 1 is the entry bar and skipped under NEXT_BAR; bar 2 decides.
    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_dt == at(2)


# ambiguous bars

def test_ambiguous_bar_is_excluded_by_default() -> None:
    trade = _one([QUIET, HITS_BOTH], long_position())

    assert trade.outcome == PositionOutcome.AMBIGUOUS.value
    assert math.isnan(trade.close_price)
    assert trade.close_dt == at(1)


def test_ambiguous_bar_assumed_stop_loss() -> None:
    trade = _one([QUIET, HITS_BOTH], long_position(), ambiguity_policy=AmbiguityPolicy.ASSUME_SL)

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value
    assert trade.close_price == 1.0980


def test_ambiguous_bar_assumed_take_profit() -> None:
    trade = _one([QUIET, HITS_BOTH], long_position(), ambiguity_policy=AmbiguityPolicy.ASSUME_TP)

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_price == 1.1040


def test_ambiguity_policy_only_matters_when_both_levels_are_hit_on_one_bar() -> None:
    trade = _one([QUIET, HITS_TP_LONG], long_position(), ambiguity_policy=AmbiguityPolicy.ASSUME_SL)

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value


# time stop and end of data

def test_time_stop_closes_at_the_last_bar_before_exit_dt() -> None:
    rows = [QUIET, QUIET, (1.1000, 1.1010, 1.0990, 1.1007), HITS_TP_LONG]

    trade = _one(rows, long_position(exit_dt=at(3)))

    # Bar 3 opens at exit_dt, so its TP is never reached.
    assert trade.outcome == PositionOutcome.MANUAL_CLOSE.value
    assert trade.close_price == 1.1007
    assert trade.close_dt == at(3)


def test_time_stop_inside_a_bar_still_trades_that_bar() -> None:
    rows = [QUIET, QUIET, HITS_TP_LONG, QUIET]

    trade = _one(rows, long_position(exit_dt=at(2) + pd.Timedelta("2min")))

    assert trade.outcome == PositionOutcome.TAKE_PROFIT_HIT.value
    assert trade.close_dt == at(2)


def test_hit_before_the_time_stop_wins() -> None:
    trade = _one([QUIET, HITS_SL_LONG, QUIET, QUIET], long_position(exit_dt=at(3)))

    assert trade.outcome == PositionOutcome.STOP_LOSS_HIT.value


def test_time_stop_right_after_the_entry_bar_closes_at_the_entry_bar_close() -> None:
    trade = _one([QUIET, HITS_TP_LONG], long_position(exit_dt=at(1)))

    assert trade.outcome == PositionOutcome.MANUAL_CLOSE.value
    assert trade.close_price == QUIET[3]


def test_no_hit_and_no_time_stop_closes_at_end_of_data() -> None:
    last = (1.1000, 1.1010, 1.0990, 1.1003)

    trade = _one([QUIET, QUIET, last], long_position())

    assert trade.outcome == PositionOutcome.END_OF_DATA.value
    assert trade.close_price == 1.1003
    assert trade.close_dt == at(2)


def test_time_stop_beyond_the_data_is_end_of_data_not_manual_close() -> None:
    trade = _one([QUIET, QUIET], long_position(exit_dt=at(10)))

    assert trade.outcome == PositionOutcome.END_OF_DATA.value
    assert trade.close_dt == at(1)


def test_entry_on_the_last_bar_closes_at_end_of_data() -> None:
    trade = _one([QUIET], long_position())

    assert trade.outcome == PositionOutcome.END_OF_DATA.value
    assert trade.close_dt == T0


# several positions and bad input

def test_positions_are_resolved_independently() -> None:
    # One bar hits the long's TP and, separately, the short's SL.
    rows = [QUIET, (1.1000, 1.1045, 1.0995, 1.1030)]

    trades = _trades(rows, long_position(), short_position())

    assert trades.set_index("side")["outcome"].to_dict() == {
        "long": PositionOutcome.TAKE_PROFIT_HIT.value,
        "short": PositionOutcome.STOP_LOSS_HIT.value,
    }


def test_position_opening_before_the_first_bar_is_rejected() -> None:
    with pytest.raises(ValueError, match="before the first bar"):
        _trades([QUIET], long_position(open_dt=T0 - pd.Timedelta("5min")))


def test_already_closed_position_is_rejected() -> None:
    position = long_position()
    position.close(at(1), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    with pytest.raises(ValueError, match="already closed"):
        _trades([QUIET, QUIET], position)
