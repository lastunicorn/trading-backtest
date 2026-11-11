"""Tests for `domain.market_data.historical_data.HistoricalData.summary`."""

from zoneinfo import ZoneInfo

import pandas as pd

from domain.market_data.historical_data import DataSummary, HistoricalData
from domain.market_data.symbol import EURUSD

from ._fakes import M5, bars


def test_describes_the_bars_without_them() -> None:
    utc = ZoneInfo("UTC")

    summary = HistoricalData(bars(4), M5, EURUSD, utc).summary()

    assert summary == DataSummary(symbol=EURUSD, timeframe=M5, timezone=utc,
                                  first_bar=pd.Timestamp("2026-01-05 00:00"),
                                  last_bar=pd.Timestamp("2026-01-05 00:15"), bars=4)
