"""Tests for `application.load_historical_data_use_case.load_mt5`."""

from zoneinfo import ZoneInfo

import pytest

from application.load_historical_data_use_case import load_mt5
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

from ._fakes import START, write_mt5_export

M5 = SampleSize.Parse("5m")


def test_one_export_is_resampled_to_the_timeframe(tmp_path) -> None:
    data = load_mt5(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), M5, EurUsd())

    assert len(data) == 2
    first = data.data.iloc[0]
    assert first["datetime"] == START
    assert first["open"] == pytest.approx(1.1000)
    assert first["high"] == pytest.approx(1.1006)
    assert first["low"] == pytest.approx(1.0998)
    assert first["close"] == pytest.approx(1.1005)
    assert first["tick_volume"] == 50


def test_spread_is_converted_from_points_to_pips(tmp_path) -> None:
    data = load_mt5(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), M5, EurUsd())

    assert data.data["spread"].tolist() == pytest.approx([0.5, 0.5])


def test_carries_timeframe_symbol_and_broker_clock(tmp_path) -> None:
    data = load_mt5(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), M5, EurUsd())

    assert data.timeframe == M5
    assert data.symbol.ticker == "EURUSD"
    assert data.timezone == ZoneInfo("America/New_York")


def test_a_folder_merges_its_exports_dropping_duplicate_bars(tmp_path) -> None:
    write_mt5_export(tmp_path / "EURUSD_2020_01_a.csv")
    write_mt5_export(tmp_path / "EURUSD_2020_01_b.csv")

    assert len(load_mt5(tmp_path, M5, EurUsd())) == 2


def test_reports_progress(tmp_path) -> None:
    messages = []

    load_mt5(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), M5, EurUsd(), progress=messages.append)

    assert any("EURUSD_2020_01.csv" in message for message in messages)
