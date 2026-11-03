"""Tests for `ports.mt5_file_access.mt5_frame_reader.read_frame`."""

from pathlib import Path

import pandas as pd
import pytest

from ports.mt5_file_access import BarParseError, read_frame

from ._fakes import HEADERLESS_7, MT5_HEADER_9, SEMICOLON_8, WITH_BAD_ROW, write_csv


def _dtypes(frame: pd.DataFrame) -> dict[str, str]:
    return {column: str(dtype) for column, dtype in frame.dtypes.items()}


def test_a_headerless_export_fills_a_blank_tick_volume_with_zero(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, HEADERLESS_7))

    assert _dtypes(frame) == {"datetime": "datetime64[us]", "open": "float64", "high": "float64",
                              "low": "float64", "close": "float64", "tick_volume": "int64"}
    assert list(frame["datetime"]) == [pd.Timestamp("2020-01-02 00:00"), pd.Timestamp("2020-01-02 00:01")]
    assert list(frame["tick_volume"]) == [10, 0]


def test_an_mt5_header_keeps_volume_and_a_partial_spread_as_float(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, MT5_HEADER_9))

    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "tick_volume", "volume", "spread"]
    assert _dtypes(frame)["datetime"] == "datetime64[s]"
    assert (_dtypes(frame)["volume"], _dtypes(frame)["spread"]) == ("int64", "float64")
    assert list(frame["volume"]) == [0, 5]
    assert frame["spread"].iat[0] == 20 and pd.isna(frame["spread"].iat[1])


def test_a_complete_spread_is_int64_and_eight_columns_end_in_spread(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, SEMICOLON_8))

    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "tick_volume", "spread"]
    assert _dtypes(frame)["spread"] == "int64"
    assert list(frame["spread"]) == [7, 8]


def test_not_strict_by_default_and_line_numbers_are_approximate(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(write_csv(tmp_path, WITH_BAD_ROW), on_skip=lambda *call: skipped.append(call))

    assert list(frame["tick_volume"]) == [10, 4]
    # The bad row is on line 3; the blank line before it isn't counted.
    assert skipped == [(2, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "unparsable row")]


def test_strict_raises_on_an_unparsable_row(tmp_path: Path) -> None:
    with pytest.raises(BarParseError, match="export.csv:2: unparsable row"):
        read_frame(write_csv(tmp_path, WITH_BAD_ROW), strict=True)


def test_an_empty_file_is_a_frame_with_only_datetime(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, ""))

    assert frame.empty
    assert list(frame.columns) == ["datetime"]


def test_a_file_without_date_time_and_prices_reports_every_row(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(write_csv(tmp_path, "foo,bar\n1,2\n"), on_skip=lambda *call: skipped.append(call))

    assert list(frame.columns) == ["datetime"]
    assert skipped == [(1, "", "row lacks required date/time/OHLC columns"),
                       (2, "", "row lacks required date/time/OHLC columns")]


def test_a_file_without_date_time_and_prices_raises_when_strict(tmp_path: Path) -> None:
    with pytest.raises(BarParseError, match="export.csv:1: row lacks required date/time/OHLC columns"):
        read_frame(write_csv(tmp_path, "foo,bar\n1,2\n"), strict=True)
