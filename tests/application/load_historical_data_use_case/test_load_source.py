"""Tests for `application.load_historical_data_use_case.load_source`."""

from application.load_historical_data_use_case import load_source
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

from ._fakes import write_clean_csv, write_mt5_export

M5 = SampleSize.Parse("5m")


def test_clean_csv_is_loaded_as_one(tmp_path) -> None:
    data = load_source(write_clean_csv(tmp_path / "clean.csv"), M5, EurUsd())

    assert len(data) == 2
    assert "spread" not in data.data.columns


def test_anything_else_is_loaded_as_mt5_exports(tmp_path) -> None:
    data = load_source(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), M5, EurUsd())

    assert len(data) == 2
    assert "spread" in data.data.columns
