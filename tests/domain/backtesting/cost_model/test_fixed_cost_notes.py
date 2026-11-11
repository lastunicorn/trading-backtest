"""Tests for `domain.backtesting.cost_model.FixedCost.notes` (the `CostModel` default)."""

from domain.backtesting.cost_model import FixedCost
from domain.backtesting.side import Side

from ._fakes import data, trades


def test_a_flat_cost_has_nothing_to_note() -> None:
    assert FixedCost().notes(trades((Side.LONG, 0, 1)), data()) == []
