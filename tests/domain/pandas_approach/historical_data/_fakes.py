"""Shared builders for the `domain.pandas_approach.historical_data` tests."""

import pandas as pd

from domain.sample_size import SampleSize

M5 = SampleSize.Parse("5m")


def bars(n: int = 3, **extra_columns) -> pd.DataFrame:
    """`n` valid M5 bars (datetime + float OHLC), plus any extra columns given."""
    frame = pd.DataFrame({
        "datetime": pd.date_range("2026-01-05 00:00", periods=n, freq="5min"),
        "open": [1.1000 + i * 0.0001 for i in range(n)],
        "high": [1.1005 + i * 0.0001 for i in range(n)],
        "low": [1.0995 + i * 0.0001 for i in range(n)],
        "close": [1.1002 + i * 0.0001 for i in range(n)],
    })
    for name, values in extra_columns.items():
        frame[name] = values
    return frame
