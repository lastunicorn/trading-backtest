"""Tests for `domain.pandas_approach.divergence.filter_regular_by_band`."""

import pandas as pd

from domain.pandas_approach.divergence import Category, Direction, Divergence, filter_regular_by_band

T = pd.Timestamp("2026-01-05 10:00")


def _div(category: Category, start_value: float, end_value: float) -> Divergence:
    return Divergence(category, Direction.BULLISH, T, T, start_value, end_value)


def test_regular_starting_outside_and_ending_inside_is_kept() -> None:
    low = _div(Category.REGULAR, 25, 35)
    high = _div(Category.REGULAR, 75, 65)

    assert filter_regular_by_band([low, high], 30, 70) == [low, high]


def test_regular_starting_inside_is_dropped() -> None:
    assert filter_regular_by_band([_div(Category.REGULAR, 40, 45)], 30, 70) == []


def test_regular_ending_outside_is_dropped() -> None:
    assert filter_regular_by_band([_div(Category.REGULAR, 20, 25)], 30, 70) == []


def test_band_edges_count_as_inside() -> None:
    assert filter_regular_by_band([_div(Category.REGULAR, 30, 35)], 30, 70) == []
    assert filter_regular_by_band([_div(Category.REGULAR, 25, 30)], 30, 70) == [_div(Category.REGULAR, 25, 30)]


def test_hidden_divergences_pass_through_unfiltered() -> None:
    hidden = _div(Category.HIDDEN, 50, 20)

    assert filter_regular_by_band([hidden], 30, 70) == [hidden]
