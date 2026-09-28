"""Tests for `domain.pandas_approach.frames.resample_ohlc`."""

import pandas as pd

from domain.pandas_approach.frames import resample_ohlc
from domain.sample_size import SampleSize


def _m1(n: int) -> pd.DataFrame:
    return pd.DataFrame({
        "datetime": pd.date_range("2026-01-01 00:00", periods=n, freq="1min"),
        "open": [float(i) for i in range(n)],
        "high": [float(i) + 0.5 for i in range(n)],
        "low": [float(i) - 0.5 for i in range(n)],
        "close": [float(i) + 0.25 for i in range(n)],
        "tick_volume": [1] * n,
    })


def test_broker_label_collapses_five_m1_bars_into_one_m5_bar() -> None:
    result = resample_ohlc(_m1(10), "M5")

    assert len(result) == 2
    first = result.iloc[0]
    assert first["open"] == 0.0
    assert first["high"] == 4.5
    assert first["low"] == -0.5
    assert first["close"] == 4.25
    assert first["tick_volume"] == 5


def test_sample_size_gives_the_same_result_as_the_matching_broker_label() -> None:
    frame = _m1(30)

    by_label = resample_ohlc(frame, "M15")
    by_size = resample_ohlc(frame, SampleSize.Parse("15m"))

    pd.testing.assert_frame_equal(by_label, by_size)


def test_empty_frame_gives_empty_frame() -> None:
    assert resample_ohlc(pd.DataFrame(), SampleSize.Parse("5m")).empty
