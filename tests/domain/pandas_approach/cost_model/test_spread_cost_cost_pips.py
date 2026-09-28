"""Tests for `domain.pandas_approach.cost_model.SpreadCost.cost_pips`."""

import pytest

from domain.pandas_approach.cost_model import SpreadCost
from domain.pandas_approach.side import Side

from ._fakes import data, trades

SPREADS = [0.1, 0.2, 0.3, 0.4]  # pips, one per bar


def test_long_pays_the_spread_of_its_entry_bar() -> None:
    result = SpreadCost().cost_pips(trades((Side.LONG, 1, 3)), data(SPREADS))

    assert result.tolist() == [0.2]


def test_short_pays_the_spread_of_its_exit_bar() -> None:
    result = SpreadCost().cost_pips(trades((Side.SHORT, 1, 3)), data(SPREADS))

    assert result.tolist() == [0.4]


def test_commission_is_added_to_every_trade() -> None:
    frame = trades((Side.LONG, 0, 2), (Side.SHORT, 0, 2))

    result = SpreadCost(commission_pips=0.5).cost_pips(frame, data(SPREADS))

    assert result.tolist() == pytest.approx([0.6, 0.8])


def test_result_is_aligned_to_the_trades_index() -> None:
    frame = trades((Side.LONG, 0, 1), (Side.SHORT, 0, 1)).set_index([["a", "b"]])

    result = SpreadCost().cost_pips(frame, data(SPREADS))

    assert result.index.tolist() == ["a", "b"]


def test_missing_spread_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="FixedCost"):
        SpreadCost().cost_pips(trades((Side.LONG, 0, 1)), data(spreads=None))


def test_trade_on_a_bar_without_spread_is_rejected() -> None:
    with pytest.raises(ValueError, match="no spread value"):
        SpreadCost().cost_pips(trades((Side.LONG, 1, 2)), data([0.1, float("nan"), 0.3, 0.4]))


def test_bar_without_spread_that_no_trade_touches_is_fine() -> None:
    result = SpreadCost().cost_pips(trades((Side.LONG, 0, 3)), data([0.1, float("nan"), 0.3, 0.4]))

    assert result.tolist() == [0.1]


def test_no_trades_gives_an_empty_series() -> None:
    assert SpreadCost().cost_pips(trades(), data(SPREADS)).empty
