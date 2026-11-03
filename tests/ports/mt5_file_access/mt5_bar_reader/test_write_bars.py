"""Tests for `ports.mt5_file_access.mt5_bar_reader.write_bars`."""

from datetime import datetime
from pathlib import Path

from ports.mt5_file_access import Bar, read_bars, write_bars

from ._fakes import MT5_HEADER_9, write_csv


def test_writes_mt5_shape_with_volume_and_spread_only_when_present(tmp_path: Path) -> None:
    bars = [Bar(datetime(2020, 1, 2, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=10)]

    write_bars(bars, tmp_path / "out" / "bars.csv")

    assert (tmp_path / "out" / "bars.csv").read_text() == (
        "date,time,open,high,low,close,tick_volume\n"
        "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    )


def test_a_missing_spread_is_blank_and_decimals_format_prices(tmp_path: Path) -> None:
    bars = read_bars(str(write_csv(tmp_path, MT5_HEADER_9)))

    write_bars(bars, tmp_path / "bars.csv", decimals=3)

    assert (tmp_path / "bars.csv").read_text() == (
        "date,time,open,high,low,close,tick_volume,volume,spread\n"
        "2026.07.01,00:00,1.100,1.200,1.000,1.150,17,0,20\n"
        "2026.07.01,00:01,1.100,1.200,1.000,1.150,14,5,\n"
    )


def test_reads_back_as_the_same_bars(tmp_path: Path) -> None:
    bars = read_bars(str(write_csv(tmp_path, MT5_HEADER_9)))

    write_bars(bars, tmp_path / "bars.csv")

    assert read_bars(str(tmp_path / "bars.csv")) == bars
