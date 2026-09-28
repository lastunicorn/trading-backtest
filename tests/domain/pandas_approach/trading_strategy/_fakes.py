"""Concrete strategies for the `domain.pandas_approach.trading_strategy` tests."""

from dataclasses import dataclass

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position
from domain.pandas_approach.trading_strategy import TradingStrategy
from domain.sample_size import SampleSize
from domain.symbol import EurUsd


@dataclass(frozen=True)
class DataclassStrategy(TradingStrategy):
    threshold_pips: float = 21.72
    rel_vol_min: float = 1.6

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        return []


class PlainStrategy(TradingStrategy):
    def generate_positions(self, data: HistoricalData) -> list[Position]:
        return []


def data_over(stamps: list[str]) -> HistoricalData:
    n = len(stamps)
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(stamps),
        "open": [1.1] * n, "high": [1.1] * n, "low": [1.1] * n, "close": [1.1] * n,
    })
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())
