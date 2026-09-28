"""Tests for `domain.pandas_approach.statistics.compute_statistics`."""

import math

import pytest

from domain.pandas_approach.position import PositionOutcome
from domain.pandas_approach.statistics import compute_statistics

from ._fakes import trades


def test_counts_wins_losses_and_win_rate() -> None:
    stats = compute_statistics(trades([10, -5, 20, -5]))

    assert stats["trades"] == 4
    assert stats["resolved"] == 4
    assert stats["wins"] == 2
    assert stats["losses"] == 2
    assert stats["win_rate_pct"] == 50


def test_pnl_totals_and_averages() -> None:
    stats = compute_statistics(trades([10, -5, 20, -5], cost=1.0))

    assert stats["total_net_pips"] == 20
    assert stats["total_gross_pips"] == 24
    assert stats["total_cost_pips"] == 4
    assert stats["avg_net_pips"] == 5
    assert stats["median_net_pips"] == 2.5
    assert stats["avg_win_pips"] == 15
    assert stats["avg_loss_pips"] == -5
    assert stats["expectancy_r"] == pytest.approx(0.5)
    assert stats["avg_duration_min"] == 60


def test_profit_factor_is_gross_profit_over_gross_loss() -> None:
    assert compute_statistics(trades([10, -5, 20, -5]))["profit_factor"] == 3


def test_profit_factor_without_losses_is_infinite() -> None:
    assert compute_statistics(trades([10, 20]))["profit_factor"] == math.inf


def test_success_is_net_positive_not_take_profit_hit() -> None:
    # A TP hit that nets -0.5 after costs is a loss.
    stats = compute_statistics(trades([-0.5], outcomes=["take-profit-hit"]))

    assert stats["outcome_take-profit-hit"] == 1
    assert stats["wins"] == 0
    assert stats["losses"] == 1


def test_break_even_trade_is_a_loss() -> None:
    assert compute_statistics(trades([0.0]))["losses"] == 1


def test_counts_every_outcome_including_absent_ones() -> None:
    stats = compute_statistics(trades([10, -5, -5]))

    assert stats["outcome_take-profit-hit"] == 1
    assert stats["outcome_stop-loss-hit"] == 2
    for outcome in PositionOutcome:
        assert f"outcome_{outcome.value}" in stats


def test_ambiguous_trades_are_counted_but_excluded_from_pnl() -> None:
    stats = compute_statistics(trades([10, None, -5]))

    assert stats["trades"] == 3
    assert stats["excluded_ambiguous"] == 1
    assert stats["resolved"] == 2
    assert stats["win_rate_pct"] == 50
    assert stats["total_net_pips"] == 5


def test_drawdown_and_streak_follow_open_time_not_row_order() -> None:
    frame = trades([10, -12, -3, 5]).iloc[[3, 0, 2, 1]]

    stats = compute_statistics(frame)

    assert stats["max_drawdown_pips"] == 15
    assert stats["max_consecutive_losses"] == 2


def test_no_trades_gives_zero_counts_and_nan_figures() -> None:
    stats = compute_statistics(trades([]))

    assert stats["trades"] == 0
    assert stats["wins"] == 0
    for key in ("win_rate_pct", "total_net_pips", "profit_factor", "max_drawdown_pips", "expectancy_r"):
        assert math.isnan(stats[key]), key


def test_only_ambiguous_trades_have_no_pnl() -> None:
    stats = compute_statistics(trades([None, None]))

    assert stats["trades"] == 2
    assert stats["resolved"] == 0
    assert math.isnan(stats["win_rate_pct"])
