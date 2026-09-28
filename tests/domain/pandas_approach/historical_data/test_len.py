"""Tests for `domain.pandas_approach.historical_data.HistoricalData.__len__`."""

from domain.pandas_approach.historical_data import HistoricalData
from domain.symbol import EurUsd

from ._fakes import M5, bars


def test_is_the_bar_count() -> None:
    assert len(HistoricalData(bars(7), M5, EurUsd())) == 7
