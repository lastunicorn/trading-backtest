"""Tests for `domain.pandas_approach.statistics.max_drawdown`."""

import math

from domain.pandas_approach.statistics import max_drawdown


def test_largest_peak_to_trough_drop() -> None:
    # equity: 0, 10, 5, 15, 3, 8 -> worst drop is 15 -> 3
    assert max_drawdown([10, -5, 10, -12, 5]) == 12


def test_losing_from_the_start_counts_from_zero() -> None:
    assert max_drawdown([-4, -6, 3]) == 10


def test_only_winners_have_no_drawdown() -> None:
    assert max_drawdown([1, 2, 3]) == 0


def test_no_trades_is_nan() -> None:
    assert math.isnan(max_drawdown([]))
