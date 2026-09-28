"""Tests for `domain.pandas_approach.divergence_positions.open_positions`."""

import pandas as pd

from domain.pandas_approach.divergence import Category, Direction, Divergence
from domain.pandas_approach.divergence_positions import open_positions
from domain.pandas_approach.side import Side


def _frame(n: int) -> pd.DataFrame:
    times = pd.date_range("2026-01-01", periods=n, freq="5min")
    return pd.DataFrame({
        "datetime": times,
        "open": [1.1000 + i * 0.0001 for i in range(n)],
    })


def _divergence(category: Category, direction: Direction, end_time, start_value: float,
                 end_value: float) -> Divergence:
    return Divergence(category, direction, end_time, end_time, start_value, end_value)


def test_regular_divergence_starting_below_lower_band_opens_a_long() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[10]
    divergence = _divergence(Category.REGULAR, Direction.BULLISH, end_time, 15.0, 35.0)

    result = open_positions(df, [divergence], pivot_right=3, rsi_lower=30, rsi_upper=70)

    assert len(result) == 1
    position = result[0]
    assert position.side == Side.LONG
    assert position.divergence == divergence
    entry_idx = 10 + 3 + 1
    assert position.open_time == df["datetime"].iat[entry_idx]
    assert position.open_price == df["open"].iat[entry_idx]


def test_regular_divergence_starting_above_upper_band_opens_a_short() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[10]
    divergence = _divergence(Category.REGULAR, Direction.BEARISH, end_time, 85.0, 65.0)

    result = open_positions(df, [divergence], pivot_right=3, rsi_lower=30, rsi_upper=70)

    assert len(result) == 1
    assert result[0].side == Side.SHORT


def test_hidden_divergence_is_never_opened_regardless_of_start_value() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[10]
    divergence = _divergence(Category.HIDDEN, Direction.BULLISH, end_time, 15.0, 35.0)

    result = open_positions(df, [divergence], pivot_right=3, rsi_lower=30, rsi_upper=70)

    assert result == []


def test_regular_divergence_starting_inside_the_band_is_skipped() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[10]
    divergence = _divergence(Category.REGULAR, Direction.BULLISH, end_time, 50.0, 60.0)

    result = open_positions(df, [divergence], pivot_right=3, rsi_lower=30, rsi_upper=70)

    assert result == []


def test_divergence_without_a_confirmed_future_bar_yet_is_skipped() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[18]  # 18 + pivot_right(3) + 1 == 22, past the end
    divergence = _divergence(Category.REGULAR, Direction.BULLISH, end_time, 15.0, 35.0)

    result = open_positions(df, [divergence], pivot_right=3, rsi_lower=30, rsi_upper=70)

    assert result == []


def test_entry_is_the_bar_right_after_pivot_confirmation_not_the_pivot_bar() -> None:
    df = _frame(20)
    end_time = df["datetime"].iat[5]
    divergence = _divergence(Category.REGULAR, Direction.BULLISH, end_time, 15.0, 35.0)

    result = open_positions(df, [divergence], pivot_right=0, rsi_lower=30, rsi_upper=70)

    assert len(result) == 1
    # pivot_right=0 -- confirmation is immediate, so entry is the very next bar.
    assert result[0].open_time == df["datetime"].iat[6]
