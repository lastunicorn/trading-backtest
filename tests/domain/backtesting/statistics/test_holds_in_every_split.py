"""Tests for `domain.backtesting.statistics.SplitVerdict.holds_in_every_split`."""

from domain.backtesting.statistics import SplitVerdict


def test_holds_when_every_split_is_net_positive() -> None:
    verdict = SplitVerdict(splits=("discovery", "test"), traded=("discovery", "test"),
                           net_positive=("discovery", "test"))

    assert verdict.holds_in_every_split


def test_fails_when_one_split_is_not_net_positive() -> None:
    verdict = SplitVerdict(splits=("discovery", "test"), traded=("discovery", "test"), net_positive=("discovery",))

    assert not verdict.holds_in_every_split


def test_a_split_without_trades_makes_it_fail() -> None:
    verdict = SplitVerdict(splits=("discovery", "test"), traded=("discovery",), net_positive=("discovery",))

    assert not verdict.holds_in_every_split


def test_holds_trivially_without_splits() -> None:
    assert SplitVerdict(splits=(), traded=(), net_positive=()).holds_in_every_split
