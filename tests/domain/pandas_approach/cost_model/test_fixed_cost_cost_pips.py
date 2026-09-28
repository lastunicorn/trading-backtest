"""Tests for `domain.pandas_approach.cost_model.FixedCost.cost_pips`."""

from domain.pandas_approach.cost_model import FixedCost
from domain.pandas_approach.side import Side

from ._fakes import data, trades


def test_every_trade_pays_the_same_cost() -> None:
    frame = trades((Side.LONG, 0, 1), (Side.SHORT, 1, 3))

    result = FixedCost(pips=1.7).cost_pips(frame, data())

    assert result.tolist() == [1.7, 1.7]
    assert result.index.equals(frame.index)
    assert result.dtype == "float64"


def test_needs_no_spread_column() -> None:
    assert FixedCost().cost_pips(trades((Side.LONG, 0, 1)), data(spreads=None)).tolist() == [1.7]


def test_no_trades_gives_an_empty_series() -> None:
    assert FixedCost().cost_pips(trades(), data()).empty
