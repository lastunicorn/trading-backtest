"""What each trade pays in friction, in pips.

    from domain.pandas_approach.cost_model import FixedCost, SpreadCost

    costs = FixedCost(pips=1.7).cost_pips(trades, data)      # one value per trade
    costs = SpreadCost(commission_pips=0.2).cost_pips(trades, data)

`trades` is a frame of simulated positions (`positions_to_frame`); the result
is a float Series aligned to its index, subtracted from gross pips before any
statistic is computed.

Prices in `HistoricalData` are bid. A long buys at the ask on entry and sells at
the bid on exit, so it pays the spread once, **at entry**. A short sells at the
bid and buys back at the ask, so it pays the spread once, **at exit**.
`SpreadCost` charges exactly that, using the `spread` column of the bar each
moment falls in. SL/TP are still *triggered* on bid prices; a short's stop that
the ask would have reached a little earlier is not modelled.

`FixedCost` is the default because not every source has a `spread` column.
Its 1.7 pips is the round-trip friction the Narrow Asia Fade research assumed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.side import Side

__all__ = ["CostModel", "FixedCost", "SpreadCost"]


class CostModel(ABC):
    """How much a trade pays in pips. Subclass to model new frictions."""

    @abstractmethod
    def cost_pips(self, trades: pd.DataFrame, data: HistoricalData) -> pd.Series:
        """One round-trip cost per row of `trades`, in pips, aligned to its index."""


@dataclass(frozen=True)
class FixedCost(CostModel):
    """The same round-trip cost for every trade."""

    pips: float = 1.7

    def __post_init__(self) -> None:
        if self.pips < 0:
            raise ValueError(f"cost cannot be negative, got {self.pips} pips")

    def cost_pips(self, trades: pd.DataFrame, data: HistoricalData) -> pd.Series:
        return pd.Series(self.pips, index=trades.index, dtype="float64")


@dataclass(frozen=True)
class SpreadCost(CostModel):
    """The bar's spread, charged when the trade crosses to the ask, plus a flat commission."""

    commission_pips: float = 0.0

    def __post_init__(self) -> None:
        if self.commission_pips < 0:
            raise ValueError(f"commission cannot be negative, got {self.commission_pips} pips")

    def cost_pips(self, trades: pd.DataFrame, data: HistoricalData) -> pd.Series:
        if "spread" not in data.data.columns:
            raise ValueError("SpreadCost needs a 'spread' column in the historical data; use FixedCost instead")

        is_long = trades["side"] == Side.LONG.value
        # The moment each trade touches the ask: entry for longs, exit for shorts.
        ask_moment = trades["open_dt"].where(is_long, trades["close_dt"])
        bars = data.locate(ask_moment)

        if (bars < 0).any():
            raise ValueError("every trade needs a bar at its ask-side moment; is a short still open?")

        spread = pd.Series(data.data["spread"].to_numpy()[bars], index=trades.index)
        if spread.isna().any():
            raise ValueError(f"{int(spread.isna().sum())} trade(s) fall on bars with no spread value")

        return spread + self.commission_pips
