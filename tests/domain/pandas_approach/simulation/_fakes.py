"""Shared builders for the `domain.pandas_approach.simulation` tests.

Every scenario uses a long at 1.1000 (SL 1.0980, TP 1.1040) or a short at
1.1000 (SL 1.1020, TP 1.0960), opened on the first bar at `T0`.
"""

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

T0 = pd.Timestamp("2026-01-05 10:00")

# A bar that touches neither level of either fixture position.
QUIET = (1.1000, 1.1010, 1.0990, 1.1005)


def at(bar: int) -> pd.Timestamp:
    """Open time of bar number `bar`."""
    return T0 + pd.Timedelta(minutes=5 * bar)


def data(*rows: tuple[float, float, float, float]) -> HistoricalData:
    """M5 bars from `T0`, one (open, high, low, close) tuple each."""
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    frame.insert(0, "datetime", pd.date_range(T0, periods=len(rows), freq="5min"))
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())


def long_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.LONG, sl=1.0980, tp=1.1040)
    fields.update(overrides)
    return Position(**fields)


def short_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.SHORT, sl=1.1020, tp=1.0960)
    fields.update(overrides)
    return Position(**fields)
