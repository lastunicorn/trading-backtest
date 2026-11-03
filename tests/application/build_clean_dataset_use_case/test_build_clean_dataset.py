"""Tests for `application.build_clean_dataset_use_case.build_clean_dataset`."""

from pathlib import Path

import pandas as pd

from application.build_clean_dataset_use_case import build_clean_dataset

EXPORT = "".join(f"2020.01.02,00:{minute:02d},1.1,1.2,1.0,1.15,10\n" for minute in range(10))


def test_reads_each_file_with_the_given_reader(tmp_path: Path) -> None:
    (tmp_path / "a.csv").write_text(EXPORT)
    calls = []

    def reader(path, *, strict, on_skip) -> pd.DataFrame:
        calls.append((Path(path).name, strict))
        return pd.DataFrame({"datetime": [pd.Timestamp("2020-01-02 00:00")], "open": [1.0], "high": [2.0],
                             "low": [0.5], "close": [1.5]})

    frame = build_clean_dataset(tmp_path, timeframe="M5", read_file=reader)

    assert calls == [("a.csv", False)]
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close"]


def test_reads_only_the_files_matching_the_pattern(tmp_path: Path) -> None:
    (tmp_path / "keep_2020_01.csv").write_text(EXPORT)
    (tmp_path / "other.csv").write_text("not, an, export\n")

    frame = build_clean_dataset(tmp_path, timeframe="M5", pattern="keep_*.csv")

    assert len(frame) == 2


def test_by_default_reads_every_csv_as_an_mt5_export(tmp_path: Path) -> None:
    (tmp_path / "EURUSD_2020_01.csv").write_text(EXPORT)

    frame = build_clean_dataset(tmp_path, timeframe="M5")

    assert frame["tick_volume"].tolist() == [50, 50]
