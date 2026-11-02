"""Tests for `libs.dukascopy_csv.file_discovery.pair_files`."""

from datetime import date
from pathlib import Path

import pytest

from libs.dukascopy_csv import PriceSide, find_files, pair_files

from .._fakes import write_export, write_pair


def test_bid_meets_ask_in_calendar_order(tmp_path: Path) -> None:
    write_pair(tmp_path, start="2020-02-01", end="2020-03-01")
    write_pair(tmp_path, start="2020-01-01", end="2020-02-01")

    pairs = pair_files(find_files(tmp_path))

    assert [pair.bid.start for pair in pairs] == [date(2020, 1, 1), date(2020, 2, 1)]
    assert all(pair.bid.side is PriceSide.BID and pair.ask.side is PriceSide.ASK for pair in pairs)
    assert all(pair.bid.start == pair.ask.start for pair in pairs)


def test_a_partial_period_pairs_despite_different_download_times(tmp_path: Path) -> None:
    write_export(tmp_path, "eurusd-m1-bid-2026-09-01-2026-09-21T16-57.csv")
    write_export(tmp_path, "eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv")

    [pair] = pair_files(find_files(tmp_path))

    assert pair.bid.path.name.endswith("T16-57.csv")
    assert pair.ask.path.name.endswith("T17-14.csv")


def test_instruments_and_folders_pair_separately(tmp_path: Path) -> None:
    write_pair(tmp_path / "a")
    write_pair(tmp_path / "b")
    write_pair(tmp_path / "a", "xauusd")

    assert len(pair_files(find_files(tmp_path))) == 3


def test_the_same_period_split_across_folders_does_not_pair(tmp_path: Path) -> None:
    bid, ask = write_pair(tmp_path / "2020")
    ask.rename(tmp_path / ask.name)

    with pytest.raises(FileNotFoundError, match="without the other side"):
        pair_files(find_files(tmp_path))


@pytest.mark.parametrize("side", ["bid", "ask"])
def test_a_file_without_its_partner_raises(tmp_path: Path, side: str) -> None:
    write_export(tmp_path, f"eurusd-m1-{side}-2020-01-01-2020-02-01.csv")

    with pytest.raises(FileNotFoundError, match="without the other side"):
        pair_files(find_files(tmp_path))


def test_two_files_on_one_side_raise(tmp_path: Path) -> None:
    write_pair(tmp_path)
    write_export(tmp_path, "eurusd-m1-bid-2020-01-01-2020-01-21T10-00.csv")

    with pytest.raises(ValueError, match="two Dukascopy bid files"):
        pair_files(find_files(tmp_path))


def test_no_files_is_no_pairs() -> None:
    assert pair_files([]) == []
