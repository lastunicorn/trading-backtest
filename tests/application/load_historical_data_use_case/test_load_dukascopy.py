"""Tests for `application.load_historical_data_use_case.load_dukascopy`."""

from zoneinfo import ZoneInfo

import pytest

from application.load_historical_data_use_case import load_dukascopy
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

from ._fakes import START, write_dukascopy_month

M5 = SampleSize.Parse("5m")


def test_reads_bid_prices_resampled(tmp_path) -> None:
    data = load_dukascopy([2020], M5, EurUsd(), data_dir=write_dukascopy_month(tmp_path))

    assert len(data) == 2
    assert data.data["datetime"].iat[0] == START
    assert data.data["open"].iat[0] == pytest.approx(1.1000)


def test_spread_is_converted_from_price_units_to_pips(tmp_path) -> None:
    data = load_dukascopy([2020], M5, EurUsd(), data_dir=write_dukascopy_month(tmp_path, spread=0.00002))

    assert data.data["spread"].tolist() == pytest.approx([0.2, 0.2])


def test_clock_is_utc(tmp_path) -> None:
    data = load_dukascopy([2020], M5, EurUsd(), data_dir=write_dukascopy_month(tmp_path))

    assert data.timezone == ZoneInfo("UTC")


def test_volume_columns_are_dropped_not_zero_filled(tmp_path) -> None:
    data = load_dukascopy([2020], M5, EurUsd(), data_dir=write_dukascopy_month(tmp_path))

    assert "tick_volume" not in data.data.columns
    assert "volume" not in data.data.columns


def test_no_years_is_rejected(tmp_path) -> None:
    with pytest.raises(ValueError, match="no years"):
        load_dukascopy([], M5, EurUsd(), data_dir=tmp_path)


def test_missing_year_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_dukascopy([2021], M5, EurUsd(), data_dir=write_dukascopy_month(tmp_path))
