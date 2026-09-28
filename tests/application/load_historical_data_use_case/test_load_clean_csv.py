"""Tests for `application.load_historical_data_use_case.load_clean_csv`."""

import pytest

from application.load_historical_data_use_case import load_clean_csv
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

from ._fakes import write_clean_csv


def test_reads_the_datetime_header_format(tmp_path) -> None:
    data = load_clean_csv(write_clean_csv(tmp_path / "clean.csv"), SampleSize.Parse("1m"), EurUsd())

    assert len(data) == 10
    assert data.data["tick_volume"].dtype == "Int64"
    assert "spread" not in data.data.columns


def test_same_timeframe_leaves_the_bars_unchanged(tmp_path) -> None:
    path = write_clean_csv(tmp_path / "clean.csv")

    data = load_clean_csv(path, SampleSize.Parse("1m"), EurUsd())

    assert data.data["close"].tolist() == pytest.approx([1.1001 + i * 0.0001 for i in range(10)])


def test_coarser_timeframe_resamples(tmp_path) -> None:
    data = load_clean_csv(write_clean_csv(tmp_path / "clean.csv"), SampleSize.Parse("5m"), EurUsd())

    assert len(data) == 2
    assert data.data["tick_volume"].tolist() == [50, 50]
