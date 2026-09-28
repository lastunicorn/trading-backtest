"""Tests for `domain.pandas_approach.historical_data.HistoricalData.from_frame`."""

from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from domain.pandas_approach.historical_data import HistoricalData, SpreadUnit
from domain.symbol import EurUsd, UsdJpy

from ._fakes import M5, bars


def test_float_volumes_become_nullable_integers() -> None:
    frame = bars(3, tick_volume=[31.0, float("nan"), 12.0])

    data = HistoricalData.from_frame(frame, M5, EurUsd())

    assert data.data["tick_volume"].dtype == "Int64"
    assert data.data["tick_volume"].tolist() == [31, pd.NA, 12]


def test_integer_volumes_are_kept() -> None:
    data = HistoricalData.from_frame(bars(3, volume=[1, 2, 3]), M5, EurUsd())

    assert data.data["volume"].tolist() == [1, 2, 3]


def test_fractional_volume_is_rejected_not_rounded() -> None:
    with pytest.raises(ValueError, match="non-integral"):
        HistoricalData.from_frame(bars(3, tick_volume=[31.0, 31.5, 12.0]), M5, EurUsd())


def test_integer_prices_become_float() -> None:
    frame = bars()
    frame["open"] = [1, 1, 1]

    data = HistoricalData.from_frame(frame, M5, EurUsd())

    assert data.data["open"].dtype == "float64"


def test_spread_in_pips_is_unchanged_by_default() -> None:
    data = HistoricalData.from_frame(bars(3, spread=[0.5, 0.6, 0.7]), M5, EurUsd())

    assert data.data["spread"].tolist() == [0.5, 0.6, 0.7]


def test_spread_in_points_is_converted_via_tick_size() -> None:
    # EURUSD: 1 point = 0.00001, 1 pip = 0.0001 -> 10 points per pip.
    frame = bars(3, spread=[5, 10, 17])

    data = HistoricalData.from_frame(frame, M5, EurUsd(), spread_unit=SpreadUnit.POINTS)

    assert data.data["spread"].tolist() == pytest.approx([0.5, 1.0, 1.7])


def test_spread_in_price_units_is_converted_via_pip_size() -> None:
    frame = bars(3, spread=[0.00005, 0.0001, 0.00017])

    data = HistoricalData.from_frame(frame, M5, EurUsd(), spread_unit=SpreadUnit.PRICE)

    assert data.data["spread"].tolist() == pytest.approx([0.5, 1.0, 1.7])


def test_spread_conversion_uses_the_given_symbol() -> None:
    # USDJPY: 1 point = 0.001, 1 pip = 0.01.
    data = HistoricalData.from_frame(bars(3, spread=[5, 10, 20]), M5, UsdJpy(), spread_unit=SpreadUnit.POINTS)

    assert data.data["spread"].tolist() == pytest.approx([0.5, 1.0, 2.0])


def test_source_frame_is_left_untouched() -> None:
    frame = bars(3, tick_volume=[31.0, 44.0, 12.0], spread=[5, 10, 17])
    before = frame.copy()

    HistoricalData.from_frame(frame, M5, EurUsd(), spread_unit=SpreadUnit.POINTS)

    pd.testing.assert_frame_equal(frame, before)


def test_timezone_is_passed_through() -> None:
    data = HistoricalData.from_frame(bars(), M5, EurUsd(), timezone=ZoneInfo("UTC"))

    assert data.timezone == ZoneInfo("UTC")


def test_unsorted_frame_is_still_rejected() -> None:
    frame = bars().iloc[::-1].reset_index(drop=True)

    with pytest.raises(ValueError, match="clean_frame"):
        HistoricalData.from_frame(frame, M5, EurUsd())
