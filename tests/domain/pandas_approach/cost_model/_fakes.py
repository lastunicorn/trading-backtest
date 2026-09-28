"""Shared builders for the `domain.pandas_approach.cost_model` tests."""

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, PositionOutcome, Side, positions_to_frame
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

T0 = pd.Timestamp("2026-01-05 10:00")


def at(bar: int) -> pd.Timestamp:
    return T0 + pd.Timedelta(minutes=5 * bar)


def data(spreads: list[float] | None = None, n: int = 4) -> HistoricalData:
    """`n` flat M5 bars from `T0`, with a `spread` column (pips) if given."""
    frame = pd.DataFrame({
        "datetime": pd.date_range(T0, periods=n, freq="5min"),
        "open": [1.1] * n,
        "high": [1.1] * n,
        "low": [1.1] * n,
        "close": [1.1] * n,
    })
    if spreads is not None:
        frame["spread"] = spreads
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())


def trades(*sides_open_close: tuple[Side, int, int]) -> pd.DataFrame:
    """A positions frame: one closed trade per (side, entry bar, exit bar)."""
    positions = []
    for side, entry, exit_ in sides_open_close:
        if side == Side.LONG:
            position = Position(at(entry), 1.1000, side, sl=1.0980, tp=1.1040)
            position.close(at(exit_), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)
        else:
            position = Position(at(entry), 1.1000, side, sl=1.1020, tp=1.0960)
            position.close(at(exit_), 1.0960, PositionOutcome.TAKE_PROFIT_HIT)
        positions.append(position)
    return positions_to_frame(positions)
