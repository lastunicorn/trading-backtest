"""Tests for `domain.pandas_approach.statistics.statistics_by_split`."""

from domain.pandas_approach.statistics import statistics_by_split

from ._fakes import trades


def test_one_row_for_all_then_one_per_split() -> None:
    frame = trades([10, -5, 20, -5], splits=["discovery", "discovery", "validation", "test"])

    table = statistics_by_split(frame)

    assert table.index.tolist() == ["all", "discovery", "validation", "test"]
    assert table.loc["all", "trades"] == 4
    assert table.loc["discovery", "trades"] == 2
    assert table.loc["discovery", "total_net_pips"] == 5
    assert table.loc["validation", "total_net_pips"] == 20
    assert table.loc["test", "total_net_pips"] == -5


def test_split_without_trades_still_gets_a_row() -> None:
    table = statistics_by_split(trades([10, -5], splits=["discovery", "discovery"]))

    assert table.loc["test", "trades"] == 0


def test_without_a_split_column_only_all() -> None:
    assert statistics_by_split(trades([10])).index.tolist() == ["all"]
