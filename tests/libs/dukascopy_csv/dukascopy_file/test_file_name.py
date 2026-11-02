"""Tests for `libs.dukascopy_csv.dukascopy_file.DukascopyFile.file_name`."""

from datetime import date, datetime
from pathlib import Path

import pytest

from libs.dukascopy_csv import DukascopyFile, PriceSide


@pytest.mark.parametrize("name", ["eurusd-m1-bid-2020-12-01-2021-01-01.csv",
                                  "eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv"])
def test_round_trips_a_parsed_name(name: str) -> None:
    assert DukascopyFile.parse(name).file_name() == name


def test_a_partial_download_at_midnight_keeps_its_time() -> None:
    file = DukascopyFile(Path("x"), "xauusd", "m1", PriceSide.ASK, date(2026, 9, 1), datetime(2026, 9, 21, 0, 0))

    assert file.file_name() == "xauusd-m1-ask-2026-09-01-2026-09-21T00-00.csv"
