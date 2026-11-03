"""Tests for `libs.metatrader_csv.records.write_records`."""

from datetime import datetime
from pathlib import Path

from libs.metatrader_csv import MetatraderRecord, read_records, write_records

from .._fakes import MT5_HEADER_9, write_csv


def test_volume_and_spread_columns_only_when_some_record_has_them(tmp_path: Path) -> None:
    records = [MetatraderRecord(datetime(2020, 1, 2, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=10, volume=0)]

    write_records(records, tmp_path / "out" / "export.csv")

    assert (tmp_path / "out" / "export.csv").read_text() == (
        "date,time,open,high,low,close,tick_volume\n"
        "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n"
    )


def test_missing_values_are_blank_and_decimals_format_prices(tmp_path: Path) -> None:
    records = [
        MetatraderRecord(datetime(2020, 1, 2, 0, 0), 1.1, 1.2, 1.0, 1.15, volume=3, spread=2),
        MetatraderRecord(datetime(2020, 1, 2, 0, 1), 1.1, 1.2, 1.0, 1.15, tick_volume=4),
    ]

    write_records(records, tmp_path / "export.csv", decimals=3)

    assert (tmp_path / "export.csv").read_text() == (
        "date,time,open,high,low,close,tick_volume,volume,spread\n"
        "2020.01.02,00:00,1.100,1.200,1.000,1.150,,3,2\n"
        "2020.01.02,00:01,1.100,1.200,1.000,1.150,4,,\n"
    )


def test_reads_back_as_the_same_records(tmp_path: Path) -> None:
    records = read_records(write_csv(tmp_path, MT5_HEADER_9))

    write_records(records, tmp_path / "copy.csv")

    assert read_records(tmp_path / "copy.csv") == records
