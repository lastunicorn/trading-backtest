"""What each trade pays in friction, in pips.

    from domain.backtesting.cost_model import FixedCost, SpreadCost

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
the ask would have reached a little earlier is not modelled. A bar with no
spread value (Dukascopy has whole days without ask prices) is charged no
spread, and `notes` says which trades that happened to.

`notes` is how a cost model reports what the numbers alone don't show; the
backtest report prints them at its end. `parameters()` is what describes it in
a run's record: a dataclass cost model's fields, like a strategy's.

`FixedCost` is the default because not every source has a `spread` column.
Its 1.7 pips is the round-trip friction the Narrow Asia Fade research assumed.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, is_dataclass

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.backtesting.side import Side

__all__ = ["CostModel", "FixedCost", "SpreadCost"]


class CostModel(ABC):
    """How much a trade pays in pips. Subclass to model new frictions."""

    @abstractmethod
    def cost_pips(self, trades: pd.DataFrame, data: HistoricalData) -> pd.Series:
        """One round-trip cost per row of `trades`, in pips, aligned to its index."""

    def notes(self, trades: pd.DataFrame, data: HistoricalData) -> list[str]:
        """What a reader of the results should know about how `trades` were charged; none by default."""
        return []

    def parameters(self) -> dict[str, object]:
        """The settings that define this cost model: a dataclass's fields, else none. Override for anything else."""
        return {field.name: getattr(self, field.name) for field in fields(self)} if is_dataclass(self) else {}


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
        return self._spread(trades, data).fillna(0.0) + self.commission_pips

    def notes(self, trades: pd.DataFrame, data: HistoricalData) -> list[str]:
        """One note naming the trades charged no spread because their bar had none, if any."""
        missing = self._spread(trades, data).isna()
        if not missing.any():
            return []

        opened = sorted(trades.loc[missing, "open_dt"])
        shown = ", ".join(f"{dt:%Y-%m-%d %H:%M}" for dt in opened[:_NOTE_TRADES_SHOWN])
        more = f" and {len(opened) - _NOTE_TRADES_SHOWN} more" if len(opened) > _NOTE_TRADES_SHOWN else ""
        return [f"{len(opened)} trade(s) charged 0 spread: their ask-side bar has no spread value "
                f"(e.g. no ask price in the source). Opened {shown}{more}."]

    def _spread(self, trades: pd.DataFrame, data: HistoricalData) -> pd.Series:
        """The spread of each trade's ask-side bar, in pips; NaN where that bar has none."""
        if "spread" not in data.data.columns:
            raise ValueError("SpreadCost needs a 'spread' column in the historical data; use FixedCost instead")

        is_long = trades["side"] == Side.LONG.value
        # The moment each trade touches the ask: entry for longs, exit for shorts.
        ask_moment = trades["open_dt"].where(is_long, trades["close_dt"])
        bars = data.locate(ask_moment)

        if (bars < 0).any():
            raise ValueError("every trade needs a bar at its ask-side moment; is a short still open?")

        return pd.Series(data.data["spread"].to_numpy(dtype="float64", na_value=float("nan"))[bars],
                         index=trades.index)


# How many open times a missing-spread note lists before "and N more".
_NOTE_TRADES_SHOWN = 10
