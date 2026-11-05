"""Tests for `ui.frame_table_view.build_rows`."""

import pandas as pd

from ui.frame_table_view import build_rows


def _frame(**columns) -> pd.DataFrame:
    return pd.DataFrame({
        "datetime": [pd.Timestamp("2020-01-02 00:00")],
        "open": [1.1], "high": [1.2], "low": [1.0], "close": [1.15],
        **columns,
    })


def test_mt5_columns_show_tick_volume_and_spread() -> None:
    header, rows = build_rows(_frame(tick_volume=[10], volume=[0], spread=[5]), decimals=5)

    assert header == ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL", "SPREAD"]
    assert rows == [["2020.01.02", "00:00", "1.10000", "1.20000", "1.00000", "1.15000", "10", "5"]]


def test_a_frame_without_tick_volume_shows_ohlc_only() -> None:
    header, rows = build_rows(_frame(), decimals=None)

    assert header == ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE"]
    assert rows == [["2020.01.02", "00:00", "1.1", "1.2", "1.0", "1.15"]]


def test_a_fractional_spread_is_rounded_not_truncated() -> None:
    _, rows = build_rows(_frame(spread=[1.99999]), decimals=None)

    assert rows[0][-1] == "2"
