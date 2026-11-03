"""Tests for `application.build_clean_dataset_use_case.build_clean_dataset`."""

from pathlib import Path

import pandas as pd

from application.build_clean_dataset_use_case import build_clean_dataset
from domain.sample_size import SampleSize

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


def _bars(day: str, price: float, minutes: int = 2) -> str:
    """`minutes` M1 bars from 00:00 on `day`, all at `price` (high +0.01, low -0.01)."""
    return "".join(
        f"{day},00:{minute:02d},{price},{price + 0.01},{price - 0.01},{price},10\n" for minute in range(minutes)
    )


def test_a_bar_spanning_two_files_gets_both_files_data(tmp_path: Path) -> None:
    # Wednesday 2025-04-30 and Thursday 2025-05-01 fall in one week (labelled Sunday 05-04).
    (tmp_path / "EURUSD_2025_04.csv").write_text(_bars("2025.04.30", 1.10))
    (tmp_path / "EURUSD_2025_05.csv").write_text(_bars("2025.05.01", 1.20))

    frame = build_clean_dataset(tmp_path, timeframe=SampleSize.Parse("1w"))

    assert len(frame) == 1
    week = frame.iloc[0]
    assert (week["open"], week["close"]) == (1.10, 1.20)
    assert (week["high"], week["low"]) == (1.21, 1.09)
    assert week["tick_volume"] == 40


def test_where_files_overlap_the_later_file_wins_each_m1_bar(tmp_path: Path) -> None:
    (tmp_path / "a_2025_04.csv").write_text(_bars("2025.04.30", 1.10, minutes=4))
    (tmp_path / "b_2025_04.csv").write_text(_bars("2025.04.30", 1.20, minutes=2))

    frame = build_clean_dataset(tmp_path, timeframe="M5")

    bar = frame.iloc[0]
    assert (bar["open"], bar["close"]) == (1.20, 1.10)
    assert bar["tick_volume"] == 40
