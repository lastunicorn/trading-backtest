"""Tests for `domain.pandas_approach.backtest.Backtest.run`."""

import pytest

from domain.pandas_approach.backtest import Backtest
from domain.pandas_approach.cost_model import FixedCost
from domain.pandas_approach.position import FRAME_COLUMNS
from domain.pandas_approach.simulation import AmbiguityPolicy, ResolveFrom
from domain.pandas_approach.trade_results import RESULT_COLUMNS

from ._fakes import ScriptedStrategy, data, day


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


def test_resolve_from_is_passed_through() -> None:
    entry_bar_hits_tp = data(10, {})
    entry_bar_hits_tp.data.loc[0, "high"] = 1.1025

    next_bar = Backtest(ScriptedStrategy([0]), entry_bar_hits_tp).run()
    entry_bar = Backtest(ScriptedStrategy([0]), entry_bar_hits_tp, resolve_from=ResolveFrom.ENTRY_BAR).run()

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
