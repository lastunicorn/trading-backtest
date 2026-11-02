"""Tests for `libs.dukascopy_csv.dukascopy_reader.read_file`."""

from pathlib import Path

import pandas as pd
import pytest

from libs.dukascopy_csv import DukascopyFile, DukascopyFormatError, read_file

from .._fakes import epoch_ms, write_export

NAME = "eurusd-m1-bid-2020-01-01-2020-02-01.csv"


def test_timestamp_becomes_a_utc_datetime_and_prices_are_kept(tmp_path: Path) -> None:
    path = write_export(tmp_path, NAME, {"2020-01-01 00:00": (1.1000, 1.1005, 1.0995, 1.1002)})

    frame = read_file(path)

    assert list(frame.columns) == ["datetime", "open", "high", "low", "close"]
    assert frame["datetime"].iat[0] == pd.Timestamp("2020-01-01 00:00", tz="UTC")
    assert tuple(frame.iloc[0, 1:]) == pytest.approx((1.1000, 1.1005, 1.0995, 1.1002))


def test_accepts_a_dukascopy_file(tmp_path: Path) -> None:
    path = write_export(tmp_path, NAME, {"2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1)})

    assert len(read_file(DukascopyFile.parse(path))) == 1


def test_rows_are_kept_as_stored_unsorted_and_with_duplicates(tmp_path: Path) -> None:
    path = write_export(tmp_path, NAME)
    with path.open("a") as out:
        for stamp, price in (("2020-01-01 00:02", 1.3), ("2020-01-01 00:01", 1.2), ("2020-01-01 00:01", 1.25)):
            out.write(f"{epoch_ms(stamp)},{price},{price},{price},{price}\n")

    frame = read_file(path)

    assert list(frame["close"]) == [1.3, 1.2, 1.25]


def test_extra_columns_are_kept(tmp_path: Path) -> None:
    path = write_export(tmp_path, NAME, {"2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1, 42.5)},
                        header="timestamp,open,high,low,close,volume")

    frame = read_file(path)

    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "volume"]
    assert frame["volume"].iat[0] == 42.5


def test_a_header_only_file_is_an_empty_frame(tmp_path: Path) -> None:
    frame = read_file(write_export(tmp_path, NAME))

    assert frame.empty
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close"]


def test_a_missing_column_raises(tmp_path: Path) -> None:
    path = write_export(tmp_path, NAME, header="timestamp,open,high,low")

    with pytest.raises(DukascopyFormatError, match="missing column.*close"):
        read_file(path)


def test_a_timestamp_that_is_not_epoch_milliseconds_raises(tmp_path: Path) -> None:
    path = tmp_path / NAME
    path.write_text("timestamp,open,high,low,close\n2020-01-01 00:00,1,1,1,1\n")

    with pytest.raises(DukascopyFormatError, match="epoch milliseconds"):
        read_file(path)

