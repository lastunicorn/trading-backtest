"""Tests for `domain.pandas_approach.splits.assign_splits`."""

from datetime import date

import pandas as pd
import pytest

from domain.pandas_approach.splits import assign_splits

BY_DATE = {
    date(2026, 1, 5): "discovery",
    date(2026, 1, 6): "validation",
    date(2026, 1, 7): "test",
}


def test_each_trade_gets_the_split_of_the_day_it_opens() -> None:
    open_dts = pd.Series(pd.to_datetime(["2026-01-07 09:00", "2026-01-05 23:55", "2026-01-06 00:00"]))

    assert assign_splits(open_dts, BY_DATE).tolist() == ["test", "discovery", "validation"]


def test_result_keeps_the_input_index() -> None:
    open_dts = pd.Series(pd.to_datetime(["2026-01-05 10:00"]), index=[42])

    assert assign_splits(open_dts, BY_DATE).index.tolist() == [42]


def test_trade_on_an_uncovered_date_is_rejected() -> None:
    open_dts = pd.Series(pd.to_datetime(["2026-01-05 10:00", "2026-01-09 10:00"]))

    with pytest.raises(ValueError, match="2026-01-09"):
        assign_splits(open_dts, BY_DATE)


def test_no_trades_gives_an_empty_series() -> None:
    assert assign_splits(pd.Series([], dtype="datetime64[us]"), BY_DATE).empty
