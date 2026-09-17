"""Tests for `domain.pandas_approach.frames.clean_frame`."""

import pandas as pd

from domain.pandas_approach.frames import clean_frame


def test_drops_duplicate_timestamp_keeping_the_last() -> None:
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:00"]),
        "close": [1.0, 2.0],
    })

    result = clean_frame(frame)

    assert len(result) == 1
    assert result["close"].iloc[0] == 2.0


def test_sorts_out_of_order_rows() -> None:
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-01 00:05", "2026-01-01 00:00"]),
        "close": [2.0, 1.0],
    })

    result = clean_frame(frame)

    assert list(result["close"]) == [1.0, 2.0]


def test_leaves_non_duplicate_rows_unchanged() -> None:
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:05"]),
        "close": [1.0, 2.0],
    })

    result = clean_frame(frame)

    assert list(result["close"]) == [1.0, 2.0]


def test_stable_sort_keeps_original_order_among_duplicates() -> None:
    # Row order before sorting: dup#1 (close=1), other, dup#2 (close=3).
    # After a stable sort on datetime, the two duplicates land adjacent in
    # their original relative order, so drop_duplicates(keep="last") must
    # keep dup#2 (close=3), not dup#1.
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-01 00:00", "2026-01-01 00:05", "2026-01-01 00:00"]),
        "close": [1.0, 2.0, 3.0],
    })

    result = clean_frame(frame)

    assert list(result["close"]) == [3.0, 2.0]


def test_empty_frame_stays_empty() -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime([]), "close": []})

    result = clean_frame(frame)

    assert result.empty
