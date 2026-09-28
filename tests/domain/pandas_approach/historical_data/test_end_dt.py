"""Tests for `domain.pandas_approach.historical_data.HistoricalData.end_dt`."""

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.symbol import EurUsd

from ._fakes import M5, bars


def test_is_the_last_bar_open_time() -> None:
    assert HistoricalData(bars(4), M5, EurUsd()).end_dt == pd.Timestamp("2026-01-05 00:15")
