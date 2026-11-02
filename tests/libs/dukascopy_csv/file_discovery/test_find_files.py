"""Tests for `libs.dukascopy_csv.file_discovery.find_files`."""

from datetime import date
from pathlib import Path

import pytest

from libs.dukascopy_csv import PriceSide, find_files

from .._fakes import write_export, write_pair


def test_a_folder_is_searched_recursively_and_sorted(tmp_path: Path) -> None:
    write_pair(tmp_path / "eurusd" / "2021", start="2021-01-01", end="2021-02-01")
    write_pair(tmp_path / "eurusd" / "2020", start="2020-12-01", end="2021-01-01")
    write_pair(tmp_path / "xauusd" / "2020", "xauusd")

    files = find_files(tmp_path)

    assert [(f.instrument, f.start, f.side) for f in files] == [
        ("eurusd", date(2020, 12, 1), PriceSide.ASK),
        ("eurusd", date(2020, 12, 1), PriceSide.BID),
        ("eurusd", date(2021, 1, 1), PriceSide.ASK),
        ("eurusd", date(2021, 1, 1), PriceSide.BID),
        ("xauusd", date(2020, 1, 1), PriceSide.ASK),
        ("xauusd", date(2020, 1, 1), PriceSide.BID),
    ]


def test_other_files_are_skipped(tmp_path: Path) -> None:
    write_pair(tmp_path)
    (tmp_path / "ANOMALIES.md").write_text("# notes\n")
    (tmp_path / "notes.csv").write_text("x\n")

    assert len(find_files(tmp_path)) == 2


def test_an_empty_folder_is_an_empty_list(tmp_path: Path) -> None:
    assert find_files(tmp_path) == []


def test_a_file_is_the_one_export(tmp_path: Path) -> None:
    bid, _ = write_pair(tmp_path)

    assert [file.path for file in find_files(bid)] == [bid]


def test_a_file_not_named_like_an_export_raises(tmp_path: Path) -> None:
    path = write_export(tmp_path, "EURUSD_2020_01.csv")

    with pytest.raises(ValueError, match="not a Dukascopy export"):
        find_files(path)


def test_a_missing_path_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no Dukascopy export"):
        find_files(tmp_path / "nope")
