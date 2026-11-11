"""Tests for `domain.market_data.historical_data.HistoricalData.__len__`."""

from domain.market_data.historical_data import HistoricalData
from domain.market_data.symbol import EURUSD

from ._fakes import M5, bars


def test_is_the_bar_count() -> None:
    assert len(HistoricalData(bars(7), M5, EURUSD)) == 7
