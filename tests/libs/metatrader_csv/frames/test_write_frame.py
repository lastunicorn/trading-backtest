"""Tests for `libs.metatrader_csv.frames.write_frame`."""

from pathlib import Path

import pandas as pd

from libs.metatrader_csv import read_frame, write_frame

from .._fakes import MT5_HEADER_9, write_csv


def test_splits_datetime_and_keeps_other_columns_as_named(tmp_path: Path) -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2020-01-02 00:00"]), "open": [1.1], "high": [1.2],
                          "low": [1.0], "close": [1.15], "my_column": ["x"]})

    write_frame(frame, tmp_path / "out" / "export.csv")

    assert (tmp_path / "out" / "export.csv").read_text() == (
        "date,time,open,high,low,close,my_column\n"
        "2020.01.02,00:00,1.1,1.2,1.0,1.15,x\n"
    )


def test_decimals_format_only_prices(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, MT5_HEADER_9))

    write_frame(frame, tmp_path / "export.csv", decimals=2)

    assert (tmp_path / "export.csv").read_text().splitlines()[1:] == [
        "2026.07.01,00:00,1.10,1.20,1.00,1.15,17,0,20",
        "2026.07.01,00:01,1.10,1.20,1.00,1.15,14,5,",
    ]


def test_reads_back_as_the_same_frame(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, MT5_HEADER_9))

    write_frame(frame, tmp_path / "copy.csv")

    pd.testing.assert_frame_equal(read_frame(tmp_path / "copy.csv"), frame, check_dtype=False)
