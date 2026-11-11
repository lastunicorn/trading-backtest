"""Tests for `domain.indicators.rsi.rsi`."""

import math

import numpy as np
import pandas as pd
import pytest

from domain.indicators.rsi import rsi

NAN = float("nan")

# length=3 on six closes, worked by hand from doc/architecture/domain/indicators.md §1:
#   delta     NaN  1  2  -1  3  -1
#   gain      NaN  1  2   0  3   0
#   loss      NaN  0  0   1  0   1
#   avg_gain   -   -  -   1     (1*2 + 3)/3 = 5/3      (5/3*2 + 0)/3 = 10/9
#   avg_loss   -   -  -  1/3    (1/3*2 + 0)/3 = 2/9    (2/9*2 + 1)/3 = 13/27
#   rs         -   -  -   3     15/2                   30/13
#   rsi        -   -  -  75     100 - 100/(17/2)       100 - 100/(43/13)
HAND_CLOSE = [10.0, 11.0, 13.0, 12.0, 15.0, 14.0]
HAND_RSI = [NAN, NAN, NAN, 75.0, 1500 / 17, 3000 / 43]


def _spec_rsi(close: list[float], length: int) -> list[float]:
    """The spec's RSI as a plain loop, to check the vectorized recursion against."""
    delta = [NAN] + [b - a for a, b in zip(close, close[1:])]
    gain = [NAN] + [max(d, 0.0) for d in delta[1:]]
    loss = [NAN] + [max(-d, 0.0) for d in delta[1:]]

    def wilder(x: list[float]) -> list[float]:
        avg = [NAN] * len(x)
        if len(x) <= length:
            return avg
        avg[length] = sum(x[1:length + 1]) / length
        for i in range(length + 1, len(x)):
            avg[i] = (avg[i - 1] * (length - 1) + x[i]) / length
        return avg

    return [100 - 100 / (1 + g / l) for g, l in zip(wilder(gain), wilder(loss))]


def test_matches_the_hand_computed_example() -> None:
    result = rsi(pd.Series(HAND_CLOSE), length=3)

    pd.testing.assert_series_equal(result, pd.Series(HAND_RSI), rtol=1e-12)


def test_first_length_values_are_nan_and_the_next_one_is_not() -> None:
    result = rsi(pd.Series(HAND_CLOSE), length=3)

    assert result.iloc[:3].isna().all()
    assert not math.isnan(result.iloc[3])


def test_seed_is_the_simple_mean_of_the_gains_and_losses_after_the_leading_nan() -> None:
    # Gains 4, 0, 0 and losses 0, 1, 1 over positions 1..3: averages 4/3 and 2/3, rs = 2.
    # A plain ewm seeded from the first delta alone would give 16/9 and 5/9, rs = 3.2 (~76.2).
    result = rsi(pd.Series([10.0, 14.0, 13.0, 12.0]), length=3)

    assert result.iloc[3] == pytest.approx(100 - 100 / 3)


def test_default_length_is_14() -> None:
    result = rsi(pd.Series(np.linspace(1.0, 2.0, 20)))

    assert result.iloc[:14].isna().all()
    assert result.iloc[14:].notna().all()


@pytest.mark.parametrize("n", [0, 1, 2, 3])
def test_series_of_length_values_or_fewer_is_all_nan(n: int) -> None:
    result = rsi(pd.Series(HAND_CLOSE[:n], dtype=float), length=3)

    assert len(result) == n
    assert result.isna().all()


def test_series_of_length_plus_one_values_has_only_the_seed() -> None:
    result = rsi(pd.Series(HAND_CLOSE[:4]), length=3)

    pd.testing.assert_series_equal(result, pd.Series(HAND_RSI[:4]), rtol=1e-12)


def test_matches_the_spec_recursion_on_a_long_series() -> None:
    rng = np.random.default_rng(7)
    close = list(1.1 + np.cumsum(rng.normal(0.0, 0.0005, 300)))

    result = rsi(pd.Series(close), length=14)

    pd.testing.assert_series_equal(result, pd.Series(_spec_rsi(close, 14)), rtol=1e-9)


def test_no_losses_gives_100() -> None:
    result = rsi(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]), length=3)

    assert (result.iloc[3:] == 100.0).all()


def test_no_gains_gives_0() -> None:
    result = rsi(pd.Series([6.0, 5.0, 4.0, 3.0, 2.0, 1.0]), length=3)

    assert (result.iloc[3:] == 0.0).all()


def test_flat_series_gives_nan() -> None:
    # Both averages are zero, so rs is 0/0.
    result = rsi(pd.Series([1.0] * 6), length=3)

    assert result.isna().all()


def test_result_keeps_the_input_index() -> None:
    index = pd.date_range("2026-01-05", periods=len(HAND_CLOSE), freq="5min")

    result = rsi(pd.Series(HAND_CLOSE, index=index), length=3)

    pd.testing.assert_series_equal(result, pd.Series(HAND_RSI, index=index), rtol=1e-12)
