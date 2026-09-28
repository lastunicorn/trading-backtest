"""Builders for the backtest tests, in two sets.

Multi-day runs (`data`, `ScriptedStrategy`): M5 bars, one trading day each at
10:00-10:25 for `days` consecutive days. The strategy opens a long at 10:00 on
each listed day (SL -20 pips, TP +20 pips); bar 10:05 of a "win" day hits TP,
of a "loss" day hits SL.

Exit rules (`bars`, `Replay`, `long_position`, `short_position`): hand-written
M5 bars from `T0`, and a long at 1.1000 (SL 1.0980, TP 1.1040) or a short at
1.1000 (SL 1.1020, TP 1.0960), opened on the first bar.
"""

from datetime import date

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.pandas_approach.trading_strategy import TradingStrategy
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

FIRST_DAY = pd.Timestamp("2026-01-05")
QUIET = (1.1000, 1.1005, 1.0995, 1.1000)
UP = (1.1000, 1.1025, 1.0995, 1.1020)
DOWN = (1.1000, 1.1005, 1.0975, 1.0980)


def day(i: int) -> pd.Timestamp:
    return FIRST_DAY + pd.Timedelta(days=i)


def data(days: int, results: dict[int, str]) -> HistoricalData:
    """`results` maps a day number to "win" or "loss"; other days are quiet."""
    rows = []
    for i in range(days):
        second = {"win": UP, "loss": DOWN}.get(results.get(i), QUIET)
        for k, bar in enumerate([QUIET, second, QUIET, QUIET, QUIET, QUIET]):
            rows.append((day(i) + pd.Timedelta(hours=10, minutes=5 * k), *bar))
    frame = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close"])
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())


class ScriptedStrategy(TradingStrategy):
    """Opens a long at 10:00 on each of `entry_days`, listed in any order."""

    def __init__(self, entry_days: list[int], only_split_over: list[date] | None = None) -> None:
        self.entry_days = entry_days
        self.only_split_over = only_split_over

    def parameters(self) -> dict[str, object]:
        return {"entry_days": self.entry_days}

    def split_days(self, data: HistoricalData):
        if self.only_split_over is not None:
            return self.only_split_over
        return super().split_days(data)

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        return [
            Position(day(i) + pd.Timedelta(hours=10), 1.1000, Side.LONG, sl=1.0980, tp=1.1020)
            for i in self.entry_days
        ]


# --- exit rules -----------------------------------------------------------------

T0 = pd.Timestamp("2026-01-05 10:00")


def at(bar: int) -> pd.Timestamp:
    """Open time of bar number `bar` in `bars(...)`."""
    return T0 + pd.Timedelta(minutes=5 * bar)


def bars(*rows: tuple[float, float, float, float]) -> HistoricalData:
    """M5 bars from `T0`, one (open, high, low, close) tuple each."""
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    frame.insert(0, "datetime", pd.date_range(T0, periods=len(rows), freq="5min"))
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())


class Replay(TradingStrategy):
    """Hands back the positions it was given, whatever the data."""

    def __init__(self, *positions: Position) -> None:
        self.positions = list(positions)

    def parameters(self) -> dict[str, object]:
        return {}

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        return self.positions


def long_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.LONG, sl=1.0980, tp=1.1040)
    fields.update(overrides)
    return Position(**fields)


def short_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.SHORT, sl=1.1020, tp=1.0960)
    fields.update(overrides)
    return Position(**fields)
