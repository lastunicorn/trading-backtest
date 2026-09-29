"""Tests for `domain.pandas_approach.statistics.statistics_by_split`."""

from domain.pandas_approach.statistics import statistics_by_split

from ._fakes import trades


def test_one_row_for_all_then_one_per_split() -> None:
    frame = trades([10, -5, 20, -5], splits=["discovery", "discovery", "validation", "test"])

    table = statistics_by_split(frame, ["discovery", "validation", "test"])

    assert table.index.tolist() == ["all", "discovery", "validation", "test"]
    assert table.loc["all", "trades"] == 4
    assert table.loc["discovery", "trades"] == 2
    assert table.loc["discovery", "total_net_pips"] == 5
    assert table.loc["validation", "total_net_pips"] == 20
    assert table.loc["test", "total_net_pips"] == -5


def test_split_without_trades_still_gets_a_row() -> None:
    table = statistics_by_split(trades([10, -5], splits=["discovery", "discovery"]), ["discovery", "test"])

    assert table.loc["test", "trades"] == 0


def test_rows_follow_the_order_of_the_names_given() -> None:
    table = statistics_by_split(trades([10, -5], splits=["2026-01", "2026-02"]), ["2026-02", "2026-01"])

    assert table.index.tolist() == ["all", "2026-02", "2026-01"]


def test_without_split_names_only_all() -> None:
    assert statistics_by_split(trades([10])).index.tolist() == ["all"]
    assert statistics_by_split(trades([10], splits=["discovery"])).index.tolist() == ["all"]
