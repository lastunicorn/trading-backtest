"""Tests for `application.load_backtest_config_use_case.cost_model`."""

from application.load_backtest_config_use_case import cost_model
from ports.backtest_config_access import CostConfig
from domain.pandas_approach.cost_model import FixedCost, SpreadCost


def test_default_is_no_cost() -> None:
    assert cost_model(CostConfig()) == FixedCost(pips=0.0)


def test_without_spread_the_commission_is_the_whole_cost() -> None:
    assert cost_model(CostConfig(commission_pips=1.7)) == FixedCost(pips=1.7)


def test_with_spread_the_commission_is_added_to_the_spread() -> None:
    assert cost_model(CostConfig(spread=True, commission_pips=0.2)) == SpreadCost(commission_pips=0.2)
