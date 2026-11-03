"""Tests for `libs.metatrader_csv.frames.read_frame`."""

from pathlib import Path

import pandas as pd
import pytest

from libs.metatrader_csv import (
    AmbiguousLayoutError,
    MetatraderParseError,
    read_frame,
    read_records,
)

from .._fakes import (
    EIGHTH_IS_SPREAD,
    HEADERLESS_7,
    HEADERLESS_8,
    MT5_HEADER_9,
    WITH_BAD_ROW,
    real_exports,
    write_csv,
)


def _dtypes(frame: pd.DataFrame) -> dict[str, str]:
    return {column: str(dtype) for column, dtype in frame.dtypes.items()}


def test_counts_are_nullable_and_a_blank_is_na(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, HEADERLESS_7))

    assert _dtypes(frame) == {"datetime": "datetime64[us]", "open": "float64", "high": "float64",
                              "low": "float64", "close": "float64", "tick_volume": "Int64"}
    assert frame["tick_volume"].iat[0] == 10 and pd.isna(frame["tick_volume"].iat[1])


def test_an_mt5_header_with_every_field(tmp_path: Path) -> None:
    frame = read_frame(write_csv(tmp_path, MT5_HEADER_9))

    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "tick_volume", "volume", "spread"]
    assert list(frame["datetime"]) == [pd.Timestamp("2026-07-01 00:00"), pd.Timestamp("2026-07-01 00:01")]
    assert list(frame["tick_volume"]) == [17, 14]
    assert list(frame["volume"]) == [0, 5]
    assert frame["spread"].iat[0] == 20 and pd.isna(frame["spread"].iat[1])


def test_eight_columns_need_headerless_layouts(tmp_path: Path) -> None:
    path = write_csv(tmp_path, HEADERLESS_8)

    with pytest.raises(AmbiguousLayoutError):
        read_frame(path)
    assert list(read_frame(path, headerless_layouts=EIGHTH_IS_SPREAD)["spread"]) == [7, 8]


def test_strict_by_default_naming_the_exact_line(tmp_path: Path) -> None:
    with pytest.raises(MetatraderParseError) as raised:
        read_frame(write_csv(tmp_path, WITH_BAD_ROW))

    assert (raised.value.line_no, raised.value.line, raised.value.reason) == (
        3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "could not convert string to float: 'bad'")


def test_not_strict_drops_bad_lines_and_reports_them_exactly(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(write_csv(tmp_path, WITH_BAD_ROW), strict=False, on_skip=lambda *call: skipped.append(call))

    assert list(frame["tick_volume"]) == [10, 4]
    assert skipped == [(3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "could not convert string to float: 'bad'")]


@pytest.mark.parametrize("text", [
    "\n\n" + WITH_BAD_ROW,                                              # leading blank lines
    "\ndate,time,open,high,low,close,tick_volume\n\n" + WITH_BAD_ROW,    # a header after a blank line
    WITH_BAD_ROW + "2020.01.02,00:04,1.1,1.2\n",                         # a short line
    WITH_BAD_ROW + "2020.01.02,00:05,1.1,1.2,1.0,1.1,5,6,7,8\n" + "2020.01.02,00:06,x,1,1,1,1,1,1\n",  # long lines
    "  \n" + WITH_BAD_ROW + "2020-01-02,00:07,1,1,1,1,1\n",             # whitespace line, bad timestamp
])
def test_skips_exactly_what_iterate_records_skips(tmp_path: Path, text: str) -> None:
    path = write_csv(tmp_path, text)
    from_frame, from_records = [], []

    frame = read_frame(path, strict=False, on_skip=lambda *call: from_frame.append(call))
    records = read_records(path, strict=False, on_skip=lambda *call: from_records.append(call))

    assert from_frame == from_records
    assert list(frame["close"]) == [record.close for record in records]


@pytest.mark.parametrize("text", ["", "date,time,open,high,low,close\n"])
def test_an_empty_or_header_only_file_is_an_empty_typed_frame(tmp_path: Path, text: str) -> None:
    frame = read_frame(write_csv(tmp_path, text))

    assert frame.empty
    assert list(frame.columns)[:5] == ["datetime", "open", "high", "low", "close"]
    assert _dtypes(frame)["open"] == "float64"


def test_rows_without_date_time_and_prices_are_unparsable(tmp_path: Path) -> None:
    skipped = []
    path = write_csv(tmp_path, "foo,bar\n1,2\n")

    frame = read_frame(path, strict=False, on_skip=lambda *call: skipped.append(call))

    assert frame.empty
    assert skipped == [(1, "foo,bar", "missing field(s): open, high, low, close"),
                       (2, "1,2", "missing field(s): open, high, low, close")]
    with pytest.raises(MetatraderParseError, match="export.csv:1: missing field"):
        read_frame(path)


@pytest.mark.skipif(not real_exports(), reason="local MT export archive not available")
def test_agrees_with_read_records_on_every_real_export() -> None:
    for path in real_exports():
        frame = read_frame(path)
        records = read_records(path)

        assert len(frame) == len(records), path
        assert list(frame["close"]) == [record.close for record in records], path
        assert frame["datetime"].iat[-1] == pd.Timestamp(records[-1].dt), path
