"""Tests for `domain.pandas_approach.divergence.find_divergences`."""

import pandas as pd

from domain.pandas_approach.divergence import Category, Direction, find_divergences


def _frame(times: pd.DatetimeIndex, low: list[float], high: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"datetime": times, "low": low, "high": high})


def _times(n: int) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-01", periods=n, freq="5min")


def test_regular_bullish_divergence_on_lower_low_price_and_higher_low_oscillator() -> None:
    n = 14
    osc = [100.0] * n
    osc[2], osc[10] = 15.0, 20.0  # oscillator: higher low (20 > 15)
    low = [1.1000] * n
    low[2], low[10] = 1.2000, 1.1990  # price: lower low (1.1990 < 1.2000)
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
    )

    assert len(result) == 1
    d = result[0]
    assert (d.category, d.direction) == (Category.REGULAR, Direction.BULLISH)
    assert d.start_value == 15.0
    assert d.end_value == 20.0


def test_regular_bearish_divergence_on_higher_high_price_and_lower_high_oscillator() -> None:
    n = 14
    osc = [30.0] * n
    osc[2], osc[10] = 110.0, 100.0  # oscillator: lower high (100 < 110)
    high = [1.1000] * n
    high[2], high[10] = 1.1000, 1.1050  # price: higher high
    low = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
    )

    assert len(result) == 1
    d = result[0]
    assert (d.category, d.direction) == (Category.REGULAR, Direction.BEARISH)
    assert d.start_value == 110.0
    assert d.end_value == 100.0


def test_hidden_bullish_divergence_excluded_by_default_and_included_when_requested() -> None:
    n = 14
    osc = [100.0] * n
    osc[2], osc[10] = 30.0, 20.0  # oscillator: lower low (20 < 30)
    low = [1.1000] * n
    low[2], low[10] = 1.1990, 1.2000  # price: higher low (1.2000 > 1.1990)
    high = [1.1000] * n
    df = _frame(_times(n), low, high)

    default_result = find_divergences(
        df, pd.Series(osc), pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
    )
    assert default_result == []

    hidden_result = find_divergences(
        df, pd.Series(osc), pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
        include_hidden=True,
    )
    assert len(hidden_result) == 1
    d = hidden_result[0]
    assert (d.category, d.direction) == (Category.HIDDEN, Direction.BULLISH)


def test_no_divergence_when_price_makes_lower_low_but_oscillator_also_makes_lower_low() -> None:
    # Price and oscillator agree (both lower lows) -- not a divergence at all,
    # regular (needs oscillator higher low) or hidden (needs price higher low).
    n = 14
    osc = [100.0] * n
    osc[2], osc[10] = 20.0, 15.0
    low = [1.1000] * n
    low[2], low[10] = 1.2000, 1.1990
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
        include_hidden=True,
    )

    assert result == []


def test_no_divergence_when_price_makes_higher_high_but_oscillator_also_makes_higher_high() -> None:
    n = 14
    osc = [30.0] * n
    osc[2], osc[10] = 90.0, 100.0
    high = [1.1000] * n
    high[2], high[10] = 1.1000, 1.1050
    low = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
        include_hidden=True,
    )

    assert result == []


def test_pivot_pair_outside_range_upper_is_not_reported() -> None:
    n = 14
    osc = [100.0] * n
    osc[2], osc[10] = 15.0, 20.0
    low = [1.1000] * n
    low[2], low[10] = 1.2000, 1.1990
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=5,  # gap is 8
    )

    assert result == []


def test_pivot_requires_strictly_more_extreme_left_neighbours() -> None:
    n = 14
    osc = [100.0] * n
    osc[2], osc[10] = 15.0, 20.0
    # A left neighbour equal to the dip breaks the strict "<" pivot check,
    # so index 2 is no longer a pivot even though price/oscillator still
    # disagree in direction.
    osc[1] = 15.0
    low = [1.1000] * n
    low[2], low[10] = 1.2000, 1.1990
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
    )

    assert result == []


def test_results_are_sorted_oldest_first_across_bullish_and_bearish() -> None:
    n = 14
    osc = [50.0] * n
    # Low pivots (bullish) at 2 and 10; high pivots (bearish) at 4 and 8.
    osc[2], osc[10] = 15.0, 20.0
    osc[4], osc[8] = 80.0, 70.0
    low = [1.1000] * n
    low[2], low[10] = 1.2000, 1.1990
    high = [1.1000] * n
    high[4], high[8] = 1.1000, 1.1050

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2, range_lower=1, range_upper=60,
    )

    assert len(result) == 2
    assert result[0].direction == Direction.BEARISH  # ends at index 8
    assert result[1].direction == Direction.BULLISH  # ends at index 10
    assert result[0].end_time < result[1].end_time


def test_no_pivots_yields_no_divergences() -> None:
    n = 14
    osc = list(range(n))  # strictly increasing: no local extreme anywhere
    low = [1.1000] * n
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=2, pivot_right=2,
    )

    assert result == []


def test_series_shorter_than_pivot_window_yields_no_divergences() -> None:
    n = 5  # smaller than pivot_left + pivot_right + 1
    osc = [10.0, 20.0, 5.0, 20.0, 10.0]
    low = [1.1000] * n
    high = [1.1000] * n

    result = find_divergences(
        _frame(_times(n), low, high), pd.Series(osc),
        pivot_left=5, pivot_right=5,
    )

    assert result == []
