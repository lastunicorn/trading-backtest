"""Tests for `domain.pandas_approach.historical_data.HistoricalData.__post_init__`."""

from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from domain.pandas_approach.historical_data import HistoricalData
from domain.symbol import EurUsd

from ._fakes import M5, bars


def test_valid_frame_is_accepted_as_is() -> None:
    frame = bars()

    data = HistoricalData(frame, M5, EurUsd())

    assert data.data is frame
    assert data.timeframe == M5
    assert data.symbol.ticker == "EURUSD"


def test_timezone_defaults_to_broker_server_time() -> None:
    assert HistoricalData(bars(), M5, EurUsd()).timezone == ZoneInfo("America/New_York")


def test_optional_columns_and_extra_columns_are_accepted() -> None:
    frame = bars(
        3,
        tick_volume=pd.array([1, 2, None], dtype="Int64"),
        volume=pd.array([0, 0, 0], dtype="int64"),
        spread=[0.5, 0.6, 0.7],
        rsi=[50.0, 51.0, 52.0],
    )

    HistoricalData(frame, M5, EurUsd())


@pytest.mark.parametrize("column", ["datetime", "open", "high", "low", "close"])
def test_missing_required_column_is_rejected(column: str) -> None:
    with pytest.raises(ValueError, match="missing required"):
        HistoricalData(bars().drop(columns=column), M5, EurUsd())


def test_empty_frame_is_rejected() -> None:
    with pytest.raises(ValueError, match="no bars"):
        HistoricalData(bars(0), M5, EurUsd())


def test_non_datetime_stamps_are_rejected() -> None:
    frame = bars()
    frame["datetime"] = frame["datetime"].astype(str)

    with pytest.raises(ValueError, match="naive datetime64"):
        HistoricalData(frame, M5, EurUsd())


def test_timezone_aware_stamps_are_rejected() -> None:
    frame = bars()
    frame["datetime"] = frame["datetime"].dt.tz_localize("UTC")

    with pytest.raises(ValueError, match="naive datetime64"):
        HistoricalData(frame, M5, EurUsd())


def test_unsorted_stamps_are_rejected() -> None:
    frame = bars().iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="clean_frame"):
        HistoricalData(frame, M5, EurUsd())


def test_duplicate_stamps_are_rejected() -> None:
    frame = pd.concat([bars(2), bars(2).tail(1)], ignore_index=True)

    with pytest.raises(ValueError, match="clean_frame"):
        HistoricalData(frame, M5, EurUsd())


def test_integer_prices_are_rejected() -> None:
    frame = bars()
    frame["open"] = [1, 1, 1]

    with pytest.raises(ValueError, match="'open' must be float"):
        HistoricalData(frame, M5, EurUsd())


def test_missing_price_is_rejected() -> None:
    frame = bars()
    frame.loc[1, "low"] = float("nan")

    with pytest.raises(ValueError, match="'low' has missing values"):
        HistoricalData(frame, M5, EurUsd())


@pytest.mark.parametrize("column", ["tick_volume", "volume"])
def test_float_volume_is_rejected(column: str) -> None:
    with pytest.raises(ValueError, match=f"'{column}' must be an integer"):
        HistoricalData(bars(3, **{column: [31.0, 44.0, 12.0]}), M5, EurUsd())


def test_integer_spread_is_rejected() -> None:
    with pytest.raises(ValueError, match="'spread' must be float"):
        HistoricalData(bars(3, spread=[5, 6, 7]), M5, EurUsd())
