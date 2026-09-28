"""Tests for `domain.pandas_approach.historical_data.HistoricalData.start_dt`."""

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.symbol import EurUsd

from ._fakes import M5, bars


def test_is_the_first_bar_timestamp() -> None:
    assert HistoricalData(bars(4), M5, EurUsd()).start_dt == pd.Timestamp("2026-01-05 00:00")
