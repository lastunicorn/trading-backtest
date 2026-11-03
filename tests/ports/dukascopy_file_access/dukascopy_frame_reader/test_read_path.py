"""Tests for `ports.dukascopy_file_access.dukascopy_frame_reader.read_path`.

Finding and pairing the files is `libs.dukascopy_csv`'s and tested there; these cover
how a pair becomes bars and what `read_path` accepts.
"""

from pathlib import Path

import pandas as pd
import pytest

from ports.dukascopy_file_access import FRAME_COLUMNS, read_path

from ._fakes import write_side


def _write_pair(data_dir: Path, folder_year: int, year: int, month: int, price: float) -> None:
    for side in ("bid", "ask"):
        write_side(data_dir, folder_year, side, year, month,
                   {f"{year:04d}-{month:02d}-01 00:00": (price, price, price, price)})


def test_ohlc_from_bid_and_spread_averaged_from_ask_minus_bid(tmp_path: Path) -> None:
    write_side(tmp_path, 2020, "bid", 2020, 1, {"2020-01-01 00:00": (1.1000, 1.1005, 1.0995, 1.1002)})
    write_side(tmp_path, 2020, "ask", 2020, 1, {"2020-01-01 00:00": (1.1002, 1.1007, 1.0997, 1.1004)})

    result = read_path(tmp_path)

    assert list(result.columns) == ["datetime", *FRAME_COLUMNS]
    row = result.iloc[0]
    assert row["datetime"] == pd.Timestamp("2020-01-01 00:00")
    assert (row["open"], row["high"], row["low"], row["close"]) == pytest.approx((1.1000, 1.1005, 1.0995, 1.1002))
    assert row["spread"] == pytest.approx(0.0002)
    assert pd.isna(row["tick_volume"])
    assert pd.isna(row["volume"])


def test_datetime_is_naive_utc(tmp_path: Path) -> None:
    _write_pair(tmp_path, 2020, 2020, 1, 1.1)

    result = read_path(tmp_path)

    assert result["datetime"].dt.tz is None


def test_a_row_present_only_in_bid_keeps_the_bar_with_nan_spread(tmp_path: Path) -> None:
    write_side(tmp_path, 2020, "bid", 2020, 1, {
        "2020-01-01 00:00": (1.1000, 1.1005, 1.0995, 1.1002),
        "2020-01-01 00:01": (1.1002, 1.1006, 1.0998, 1.1003),
    })
    write_side(tmp_path, 2020, "ask", 2020, 1, {"2020-01-01 00:00": (1.1002, 1.1007, 1.0997, 1.1004)})

    result = read_path(tmp_path)

    assert len(result) == 2
    assert pd.isna(result.iloc[1]["spread"])
    assert result.iloc[1]["close"] == pytest.approx(1.1003)


def test_a_row_present_only_in_ask_is_dropped(tmp_path: Path) -> None:
    write_side(tmp_path, 2020, "bid", 2020, 1, {"2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1)})
    write_side(tmp_path, 2020, "ask", 2020, 1, {
        "2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1),
        "2020-01-01 00:01": (1.2, 1.2, 1.2, 1.2),
    })

    result = read_path(tmp_path)

    assert list(result["datetime"]) == [pd.Timestamp("2020-01-01 00:00")]


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


def test_an_empty_folder_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="no Dukascopy"):
        read_path(tmp_path)
