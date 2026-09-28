"""Tests for `domain.pandas_approach.statistics.max_consecutive_losses`."""

from domain.pandas_approach.statistics import max_consecutive_losses


def test_longest_losing_run() -> None:
    assert max_consecutive_losses([1, -1, -2, 3, -1, -1, -1, 2]) == 3


def test_zero_counts_as_a_loss() -> None:
    assert max_consecutive_losses([-1, 0, -1]) == 3


def test_no_losses_is_zero() -> None:
    assert max_consecutive_losses([1, 2]) == 0


def test_no_trades_is_zero() -> None:
    assert max_consecutive_losses([]) == 0
