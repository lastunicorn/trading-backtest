"""Tests for `domain.pandas_approach.historical_data.HistoricalData.locate`."""

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.symbol import EurUsd

from ._fakes import M5, bars

T0 = pd.Timestamp("2026-01-05 00:00")


def _data() -> HistoricalData:
    return HistoricalData(bars(3), M5, EurUsd())  # bars at 00:00, 00:05, 00:10


def test_bar_open_time_maps_to_that_bar() -> None:
    assert _data().locate([T0, T0 + pd.Timedelta("5min")]).tolist() == [0, 1]


def test_time_inside_a_bar_maps_to_that_bar() -> None:
    assert _data().locate([T0 + pd.Timedelta("7min")]).tolist() == [1]


def test_time_after_the_last_bar_maps_to_the_last_bar() -> None:
    assert _data().locate([T0 + pd.Timedelta("3D")]).tolist() == [2]


def test_time_before_the_first_bar_is_minus_one() -> None:
    assert _data().locate([T0 - pd.Timedelta("1min")]).tolist() == [-1]


def test_missing_stamps_are_minus_one() -> None:
    assert _data().locate([None, pd.NaT]).tolist() == [-1, -1]


def test_accepts_a_series_and_an_empty_input() -> None:
    data = _data()

    assert data.locate(pd.Series([T0])).tolist() == [0]
    assert data.locate([]).tolist() == []
