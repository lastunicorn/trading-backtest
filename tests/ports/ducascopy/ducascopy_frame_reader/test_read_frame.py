"""Tests for `ports.ducascopy.ducascopy_frame_reader.read_frame`."""

from pathlib import Path

import pandas as pd
import pytest

from ports.ducascopy import FRAME_COLUMNS, read_frame

from ._fakes import write_side as _write_side


def test_month_ohlc_from_bid_and_spread_averaged_from_ask_minus_bid(tmp_path: Path) -> None:
    _write_side(
        tmp_path, 2020, "bid", 2020, 1,
        {"2020-01-01 00:00": (1.1000, 1.1005, 1.0995, 1.1002)},
    )
    _write_side(
        tmp_path, 2020, "ask", 2020, 1,
        {"2020-01-01 00:00": (1.1002, 1.1007, 1.0997, 1.1004)},
    )

    result = read_frame(2020, 1, data_dir=tmp_path)

    assert list(result.columns) == ["datetime", *FRAME_COLUMNS]
    row = result.iloc[0]
    assert row["open"] == pytest.approx(1.1000)
    assert row["high"] == pytest.approx(1.1005)
    assert row["low"] == pytest.approx(1.0995)
    assert row["close"] == pytest.approx(1.1002)
    assert row["spread"] == pytest.approx(0.0002)
    assert pd.isna(row["tick_volume"])
    assert pd.isna(row["volume"])


def test_row_present_only_in_bid_keeps_the_bar_with_nan_spread(tmp_path: Path) -> None:
    _write_side(
        tmp_path, 2020, "bid", 2020, 1,
        {
            "2020-01-01 00:00": (1.1000, 1.1005, 1.0995, 1.1002),
            "2020-01-01 00:01": (1.1002, 1.1006, 1.0998, 1.1003),
        },
    )
    _write_side(
        tmp_path, 2020, "ask", 2020, 1,
        {"2020-01-01 00:00": (1.1002, 1.1007, 1.0997, 1.1004)},
    )

    result = read_frame(2020, 1, data_dir=tmp_path)

    assert len(result) == 2
    assert pd.isna(result.iloc[1]["spread"])
    assert result.iloc[1]["close"] == pytest.approx(1.1003)


def test_whole_year_concatenates_months_in_calendar_order(tmp_path: Path) -> None:
    for side in ("bid", "ask"):
        _write_side(tmp_path, 2020, side, 2020, 2, {"2020-02-01 00:00": (1.2, 1.2, 1.2, 1.2)})
        _write_side(tmp_path, 2020, side, 2020, 1, {"2020-01-01 00:00": (1.1, 1.1, 1.1, 1.1)})

    result = read_frame(2020, data_dir=tmp_path)

    assert list(result["datetime"]) == [
        pd.Timestamp("2020-01-01 00:00"),
        pd.Timestamp("2020-02-01 00:00"),
    ]


def test_finds_a_file_filed_under_the_following_years_folder(tmp_path: Path) -> None:
    # Mirrors a real Dukascopy quirk: December's export sometimes sits in the
    # next year's folder even though its data belongs to the requested year.
    for side in ("bid", "ask"):
        _write_side(tmp_path, 2026, side, 2025, 12, {"2025-12-31 23:59": (1.3, 1.3, 1.3, 1.3)})

    by_month = read_frame(2025, 12, data_dir=tmp_path)
    by_year = read_frame(2025, data_dir=tmp_path)

    assert len(by_month) == 1
    assert list(by_year["datetime"]) == [pd.Timestamp("2025-12-31 23:59")]


def test_missing_month_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        read_frame(2020, 1, data_dir=tmp_path)
