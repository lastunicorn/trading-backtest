"""Tests for `ports.ducascopy.ducascopy_frame_reader.read_path`."""

from pathlib import Path

import pandas as pd
import pytest

from ports.ducascopy import FRAME_COLUMNS, read_path

from ._fakes import write_side


def _write_pair(data_dir: Path, folder_year: int, year: int, month: int, price: float) -> None:
    for side in ("bid", "ask"):
        write_side(data_dir, folder_year, side, year, month,
                   {f"{year:04d}-{month:02d}-01 00:00": (price, price, price, price)})


def test_a_folder_is_read_recursively_in_calendar_order(tmp_path: Path) -> None:
    _write_pair(tmp_path, 2021, 2021, 1, 1.2)
    _write_pair(tmp_path, 2020, 2020, 2, 1.1)
    _write_pair(tmp_path, 2021, 2020, 12, 1.15)  # filed under the next year's folder

    result = read_path(tmp_path)

    assert list(result.columns) == ["datetime", *FRAME_COLUMNS]
    assert list(result["datetime"]) == [
        pd.Timestamp("2020-02-01 00:00"),
        pd.Timestamp("2020-12-01 00:00"),
        pd.Timestamp("2021-01-01 00:00"),
    ]


def test_one_year_folder_reads_only_that_folder(tmp_path: Path) -> None:
    _write_pair(tmp_path, 2020, 2020, 1, 1.1)
    _write_pair(tmp_path, 2021, 2021, 1, 1.2)

    result = read_path(tmp_path / "2021")

    assert list(result["datetime"]) == [pd.Timestamp("2021-01-01 00:00")]


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_either_file_reads_its_pair(tmp_path: Path, side: str) -> None:
    _write_pair(tmp_path, 2020, 2020, 1, 1.1)
    _write_pair(tmp_path, 2020, 2020, 2, 1.2)

    result = read_path(tmp_path / "2020" / f"eurusd-m1-{side}-2020-01-01-2020-02-01.csv")

    assert list(result["datetime"]) == [pd.Timestamp("2020-01-01 00:00")]
    assert result["spread"].iat[0] == pytest.approx(0.0)


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_a_file_without_its_partner_raises(tmp_path: Path, side: str) -> None:
    write_side(tmp_path, 2020, side, 2020, 1, {"2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1)})

    with pytest.raises(FileNotFoundError, match="without the other side"):
        read_path(tmp_path)


def test_a_partial_month_pairs_on_the_start_date_not_the_download_time(tmp_path: Path) -> None:
    _write_pair(tmp_path, 2026, 2026, 8, 1.1)
    folder = tmp_path / "2026"
    for side, stamp in (("bid", "16-57"), ("ask", "17-14")):
        write_side(tmp_path, 2026, side, 2026, 9, {"2026-09-01 00:00": (1.2, 1.2, 1.2, 1.2)})
        (folder / f"eurusd-m1-{side}-2026-09-01-2026-10-01.csv").rename(
            folder / f"eurusd-m1-{side}-2026-09-01-2026-09-21T{stamp}.csv")

    assert list(read_path(tmp_path)["datetime"]) == [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-09-01")]
    assert list(read_path(folder / "eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv")["datetime"]) == [
        pd.Timestamp("2026-09-01")]


def test_other_csv_files_in_the_folder_are_ignored(tmp_path: Path) -> None:
    _write_pair(tmp_path, 2020, 2020, 1, 1.1)
    (tmp_path / "notes.csv").write_text("x\n")

    assert len(read_path(tmp_path)) == 1


def test_an_empty_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no Dukascopy"):
        read_path(tmp_path)


def test_a_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no Dukascopy export"):
        read_path(tmp_path / "nope")


def test_a_file_that_is_not_a_dukascopy_export_raises(tmp_path: Path) -> None:
    path = tmp_path / "EURUSD_2020_01.csv"
    path.write_text("x\n")

    with pytest.raises(ValueError, match="not a Dukascopy export"):
        read_path(path)
