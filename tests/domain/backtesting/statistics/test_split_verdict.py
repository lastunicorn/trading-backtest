"""Tests for `domain.backtesting.statistics.split_verdict`."""

from domain.backtesting.statistics import split_verdict, statistics_by_split

from ._fakes import trades

SPLITS = ["discovery", "validation", "test"]


def test_names_every_split_after_all_in_table_order() -> None:
    table = statistics_by_split(trades([10, -5], splits=["discovery", "test"]), ["test", "discovery", "validation"])

    assert split_verdict(table).splits == ("test", "discovery", "validation")


def test_names_the_splits_that_ended_net_positive() -> None:
    table = statistics_by_split(trades([10, -5, 20, -5], splits=["discovery", "discovery", "validation", "test"]),
                                SPLITS)

    assert split_verdict(table).net_positive == ("discovery", "validation")


def test_names_the_splits_with_trades() -> None:
    table = statistics_by_split(trades([10, -5], splits=["discovery", "test"]), SPLITS)

    assert split_verdict(table).traded == ("discovery", "test")


def test_a_split_without_resolved_trades_is_traded_but_not_net_positive() -> None:
    table = statistics_by_split(trades([None], splits=["discovery"]), SPLITS)

    verdict = split_verdict(table)
    assert verdict.traded == ("discovery",)
    assert verdict.net_positive == ()


def test_a_table_with_only_all_has_no_splits() -> None:
    verdict = split_verdict(statistics_by_split(trades([10])))

    assert (verdict.splits, verdict.traded, verdict.net_positive) == ((), (), ())
