"""Tests for `libs.dukascopy_csv.dukascopy_file.DukascopyFile.parse`."""

from datetime import date, datetime
from pathlib import Path

import pytest

from libs.dukascopy_csv import DukascopyFile, PriceSide

REAL_ARCHIVE = Path("/nfs/YubabaFinance/trading/historical data/dukascopy")


def test_a_whole_period_name() -> None:
    file = DukascopyFile.parse("/data/2020/eurusd-m1-bid-2020-01-01-2020-02-01.csv")

    assert file == DukascopyFile(
        path=Path("/data/2020/eurusd-m1-bid-2020-01-01-2020-02-01.csv"),
        instrument="eurusd", timeframe="m1", side=PriceSide.BID,
        start=date(2020, 1, 1), end=date(2020, 2, 1),
    )
    assert type(file.end) is date


def test_a_partial_download_ends_at_the_download_time() -> None:
    file = DukascopyFile.parse("eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv")

    assert file.side is PriceSide.ASK
    assert file.end == datetime(2026, 9, 21, 17, 14)


@pytest.mark.parametrize("name", ["deuidxeur-m1-bid-2020-01-01-2020-02-01.csv",
                                  "xauusd-h1-ask-2020-01-01-2021-01-01.csv"])
def test_any_instrument_and_timeframe(name: str) -> None:
    assert DukascopyFile.parse(name) is not None


@pytest.mark.parametrize("name", [
    "ANOMALIES.md",
    "EURUSD_2020_01.csv",
    "eurusd-m1-mid-2020-01-01-2020-02-01.csv",
    "eurusd-m1-bid-2020-01-01-2020-02-01.json",
    "eurusd-m1-bid-2020-01-01.csv",
])
def test_other_names_are_none(name: str) -> None:
    assert DukascopyFile.parse(name) is None


@pytest.mark.skipif(not REAL_ARCHIVE.is_dir(), reason="local Dukascopy archive not available")
def test_every_csv_in_the_real_archive_parses() -> None:
    names = [path.name for path in REAL_ARCHIVE.rglob("*.csv")]

    assert names
    assert [name for name in names if DukascopyFile.parse(name) is None] == []
