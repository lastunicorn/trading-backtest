"""Per-trade P&L in pips: simulated positions plus what each one made.

    from domain.pandas_approach.trade_results import trade_results

    trades = positions_to_frame(simulate_positions(data, positions))
    trades = trade_results(trades, data.symbol, cost_model.cost_pips(trades, data))

Adds, in this order:

    gross_pips    signed move from entry to close, before costs
    cost_pips     round-trip friction (from a `CostModel`)
    net_pips      gross_pips - cost_pips; what every statistic is computed from
    risk_pips     distance from entry to SL
    net_r         net_pips / risk_pips
    duration_min  minutes from open_dt to close_dt

A trade with no close price -- AMBIGUOUS, or still OPEN -- gets NaN for
gross_pips, net_pips and net_r, so it drops out of every P&L statistic
while staying in the file and in the outcome counts.
"""

from __future__ import annotations

import pandas as pd

from domain.pandas_approach.side import Side
from domain.symbol import Symbol

__all__ = ["RESULT_COLUMNS", "trade_results"]

RESULT_COLUMNS = ("gross_pips", "cost_pips", "net_pips", "risk_pips", "net_r", "duration_min")


def trade_results(trades: pd.DataFrame, symbol: Symbol, cost_pips: pd.Series) -> pd.DataFrame:
    """A copy of `trades` with the `RESULT_COLUMNS` appended.

    `cost_pips` must be aligned to `trades`' index, as `CostModel.cost_pips`
    returns it.
    """
    if not cost_pips.index.equals(trades.index):
        raise ValueError("cost_pips must be aligned to the trades' index")

    result = trades.copy()
    direction = result["side"].map({Side.LONG.value: 1.0, Side.SHORT.value: -1.0})

    result["gross_pips"] = symbol.to_pips((result["close_price"] - result["open_price"]) * direction)
    result["cost_pips"] = cost_pips.astype("float64")
    result["net_pips"] = result["gross_pips"] - result["cost_pips"]
    result["risk_pips"] = symbol.to_pips((result["open_price"] - result["sl"]).abs())
    result["net_r"] = result["net_pips"] / result["risk_pips"]
    result["duration_min"] = (result["close_dt"] - result["open_dt"]).dt.total_seconds() / 60

    return result
