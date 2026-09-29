"""Tests for `backtest.CostConfig.model`."""

from backtest import CostConfig
from domain.pandas_approach.cost_model import FixedCost, SpreadCost


def test_default_is_no_cost() -> None:
    assert CostConfig().model() == FixedCost(pips=0.0)


def test_without_spread_the_commission_is_the_whole_cost() -> None:
    assert CostConfig(commission_pips=1.7).model() == FixedCost(pips=1.7)


def test_with_spread_the_commission_is_added_to_the_spread() -> None:
    assert CostConfig(spread=True, commission_pips=0.2).model() == SpreadCost(commission_pips=0.2)
