"""Tests for `domain.pandas_approach.position.positions_to_frame`."""

import pandas as pd

from domain.pandas_approach.position import FRAME_COLUMNS, PositionOutcome, positions_to_frame

from ._fakes import T0, long_position, short_position


def test_one_row_per_position_in_frame_column_order() -> None:
    frame = positions_to_frame([long_position(), short_position()])

    assert list(frame.columns) == list(FRAME_COLUMNS)
    assert len(frame) == 2


def test_enums_become_their_string_values() -> None:
    closed = short_position(tag="break-high")
    closed.close(T0 + pd.Timedelta("5min"), 1.1020, PositionOutcome.STOP_LOSS_HIT)

    row = positions_to_frame([closed]).iloc[0]

    assert row["side"] == "short"
    assert row["outcome"] == "stop-loss-hit"
    assert row["tag"] == "break-high"


def test_open_position_has_missing_close_fields() -> None:
    row = positions_to_frame([long_position()]).iloc[0]

    assert row["outcome"] == "open"
    assert pd.isna(row["close_dt"])
    assert pd.isna(row["close_price"])
    assert pd.isna(row["exit_dt"])


def test_values_round_trip() -> None:
    position = long_position(exit_dt=T0 + pd.Timedelta("4h"))
    position.close(T0 + pd.Timedelta("20min"), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    row = positions_to_frame([position]).iloc[0]

    assert row["open_dt"] == T0
    assert row["open_price"] == 1.1000
    assert row["sl"] == 1.0980
    assert row["tp"] == 1.1040
    assert row["exit_dt"] == T0 + pd.Timedelta("4h")
    assert row["close_dt"] == T0 + pd.Timedelta("20min")
    assert row["close_price"] == 1.1040


def test_empty_list_gives_empty_frame_with_same_columns_and_dtypes() -> None:
    empty = positions_to_frame([])
    full = positions_to_frame([long_position()])

    assert empty.empty
    assert list(empty.columns) == list(FRAME_COLUMNS)
    pd.testing.assert_series_equal(empty.dtypes, full.dtypes)


def test_datetime_columns_are_microsecond_resolution() -> None:
    frame = positions_to_frame([long_position()])

    for column in ("open_dt", "exit_dt", "close_dt"):
        assert frame[column].dtype == "datetime64[us]"
