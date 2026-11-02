"""Tests for `libs.dukascopy_csv.file_discovery.find_pair`."""

from pathlib import Path

import pytest

from libs.dukascopy_csv import find_pair

from .._fakes import write_export, write_pair


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_either_file_finds_its_pair(tmp_path: Path, side: str) -> None:
    bid, ask = write_pair(tmp_path)
    write_pair(tmp_path, start="2020-02-01", end="2020-03-01")

    pair = find_pair(bid if side == "bid" else ask)

    assert (pair.bid.path, pair.ask.path) == (bid, ask)


def test_an_unpaired_file_elsewhere_in_the_folder_is_ignored(tmp_path: Path) -> None:
    bid, ask = write_pair(tmp_path)
    write_export(tmp_path, "eurusd-m1-bid-2020-02-01-2020-03-01.csv")

    assert find_pair(ask).bid.path == bid


def test_a_missing_partner_raises(tmp_path: Path) -> None:
    path = write_export(tmp_path, "eurusd-m1-bid-2020-01-01-2020-02-01.csv")

    with pytest.raises(FileNotFoundError, match="without the other side"):
        find_pair(path)


def test_a_file_not_named_like_an_export_raises(tmp_path: Path) -> None:
    path = write_export(tmp_path, "EURUSD_2020_01.csv")

    with pytest.raises(ValueError, match="not a Dukascopy export"):
        find_pair(path)


@pytest.mark.parametrize("make", [lambda tmp: tmp / "nope.csv", lambda tmp: tmp])
def test_a_path_that_is_not_a_file_raises(tmp_path: Path, make) -> None:
    with pytest.raises(FileNotFoundError, match="no Dukascopy export"):
        find_pair(make(tmp_path))
