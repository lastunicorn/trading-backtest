"""Tests for `ports.mt5_file_access.mt5_frame_reader.read_frame`."""

from pathlib import Path

import pandas as pd
import pytest

from ports.mt5_file_access import BarParseError, iterate_bars, read_frame

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


def test_strict_by_default_naming_the_exact_line(tmp_path: Path) -> None:
    with pytest.raises(BarParseError) as raised:
        read_frame(write_csv(tmp_path, WITH_BAD_ROW))

    assert str(raised.value) == ("export.csv:3: could not convert string to float: 'bad'"
                                 "  |  2020.01.02,00:02,bad,1.2,1.0,1.1,3")


def test_not_strict_drops_bad_lines_and_reports_them_exactly(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(write_csv(tmp_path, WITH_BAD_ROW), strict=False, on_skip=lambda *call: skipped.append(call))

    assert list(frame["tick_volume"]) == [10, 4]
    assert skipped == [(3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "could not convert string to float: 'bad'")]


def test_reports_the_same_skipped_lines_as_iterate_bars(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "\n" + WITH_BAD_ROW + "2020.01.02,00:04,1.1,1.2\n2020.01.02,00:05,1.1,1.2,1.0,1.1,5,6,7,8\n")
    from_frame, from_bars = [], []

    frame = read_frame(path, strict=False, on_skip=lambda *call: from_frame.append(call))
    bars = list(iterate_bars(str(path), strict=False, on_skip=lambda *call: from_bars.append(call)))

    assert from_frame == from_bars
    assert len(from_frame) == 2
    assert list(frame["close"]) == [bar.close for bar in bars]


def test_an_empty_file_is_a_frame_with_only_datetime(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, ""))

    assert frame.empty
    assert list(frame.columns) == ["datetime"]


def test_a_file_without_date_time_and_prices_reports_every_row(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(write_csv(tmp_path, "foo,bar\n1,2\n"), strict=False, on_skip=lambda *call: skipped.append(call))

    assert list(frame.columns) == ["datetime"]
    assert skipped == [(1, "foo,bar", "missing field(s): open, high, low, close"),
                       (2, "1,2", "missing field(s): open, high, low, close")]


def test_a_file_without_date_time_and_prices_raises_when_strict(tmp_path: Path) -> None:
    with pytest.raises(BarParseError, match="export.csv:1: missing field"):
        read_frame(write_csv(tmp_path, "foo,bar\n1,2\n"))
