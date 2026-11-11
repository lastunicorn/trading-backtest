"""Tests for `domain.backtesting.cost_model.CostModel.parameters`."""

import pandas as pd

from domain.backtesting.cost_model import CostModel, FixedCost, SpreadCost


class _PlainCost(CostModel):
    """A cost model that is not a dataclass."""

    def cost_pips(self, trades, data) -> pd.Series:
        return pd.Series(0.0, index=trades.index)


def test_a_dataclass_cost_model_reports_its_fields() -> None:
    assert FixedCost(pips=0.5).parameters() == {"pips": 0.5}
    assert SpreadCost(commission_pips=0.2).parameters() == {"commission_pips": 0.2}


def test_a_plain_cost_model_reports_nothing() -> None:
    assert _PlainCost().parameters() == {}
