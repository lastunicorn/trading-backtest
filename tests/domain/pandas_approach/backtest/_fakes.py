"""A scripted strategy and flat-ish bars for the backtest tests.

Bars are M5, one trading day each at 10:00-10:25 for `days` consecutive days.
The strategy opens a long at 10:00 on each listed day (SL -20 pips, TP +20
pips); bar 10:05 of a "win" day hits TP, of a "loss" day hits SL.
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
