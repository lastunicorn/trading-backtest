"""Tests for `ports.mt5_file_access.mt5_frame_reader.write_frame`."""

from pathlib import Path

import pandas as pd

from ports.mt5_file_access import read_frame, write_frame

from ._fakes import SEMICOLON_8, write_csv


def test_splits_datetime_into_mt5_date_and_time(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, SEMICOLON_8))

    write_frame(frame, tmp_path / "out" / "frame.csv")

    assert (tmp_path / "out" / "frame.csv").read_text() == (
        "date,time,open,high,low,close,tick_volume,spread\n"
        "2020.01.02,00:00,1.1,1.2,1.0,1.15,10,7\n"
        "2020.01.02,00:01,1.1,1.2,1.0,1.15,10,8\n"
    )


def test_decimals_format_only_prices(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, SEMICOLON_8))

    write_frame(frame, tmp_path / "frame.csv", decimals=3)

    assert (tmp_path / "frame.csv").read_text().splitlines()[1] == "2020.01.02,00:00,1.100,1.200,1.000,1.150,10,7"


def test_reads_back_as_the_same_frame(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, SEMICOLON_8))

    write_frame(frame, tmp_path / "frame.csv")

    pd.testing.assert_frame_equal(read_frame(tmp_path / "frame.csv"), frame)
