"""Bars and a scripted divergence for the `strategies.rsi_divergence` tests.

`find_divergences` has its own tests; these replace it with one scripted
divergence so the strategy's own logic -- band filter, entry timing, stop and
target -- can be pinned down exactly.
"""

from datetime import tzinfo

import pandas as pd

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.divergence import Category, Direction, Divergence
from domain.pandas_approach.historical_data import HistoricalData
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

T0 = pd.Timestamp("2026-01-05 00:00")
PIVOT = 20     # the newer pivot bar
ENTRY = PIVOT + 5 + 1    # pivot_right=5, so entry opens 6 bars later


def at(bar: int) -> pd.Timestamp:
    return T0 + pd.Timedelta(minutes=15 * bar)


def data(n: int = 60, *, pivot_low: float = 1.0980, pivot_high: float = 1.1020,
         entry_open: float = 1.1000, timezone: tzinfo = BROKER_SERVER_TZ) -> HistoricalData:
    """Flat M15 bars around 1.1000, with the pivot bar's extremes and the entry bar's open set."""
    frame = pd.DataFrame({
        "datetime": pd.date_range(T0, periods=n, freq="15min"),
        "open": [1.1000] * n,
        "high": [1.1005] * n,
        "low": [1.0995] * n,
        "close": [1.1000] * n,
    })
    frame.loc[PIVOT, ["low", "high"]] = [pivot_low, pivot_high]
    frame.loc[ENTRY, "open"] = entry_open
    return HistoricalData(frame, SampleSize.Parse("15m"), EurUsd(), timezone)


def divergence(direction: Direction, start_value: float, end_value: float,
               category: Category = Category.REGULAR, end_bar: int = PIVOT) -> Divergence:
    return Divergence(category, direction, at(end_bar - 10), at(end_bar), start_value, end_value)


def script(monkeypatch, *divergences: Divergence) -> None:
    """Make the strategy's divergence scan return exactly `divergences`."""
    monkeypatch.setattr(
        "strategies.rsi_divergence.find_divergences", lambda *args, **kwargs: list(divergences)
    )
