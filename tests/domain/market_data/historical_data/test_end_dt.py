"""Tests for `domain.market_data.historical_data.HistoricalData.end_dt`."""

import pandas as pd

from domain.market_data.historical_data import HistoricalData
from domain.market_data.symbol import EURUSD

from ._fakes import M5, bars


def test_is_the_last_bar_open_time() -> None:
    assert HistoricalData(bars(4), M5, EURUSD).end_dt == pd.Timestamp("2026-01-05 00:15")
