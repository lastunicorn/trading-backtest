"""`TradingStrategy`: the base class every backtestable strategy inherits.

    @dataclass(frozen=True)
    class MyStrategy(TradingStrategy):
        threshold_pips: float = 20.0

        def generate_positions(self, data: HistoricalData) -> list[Position]:
            ...   # decide entries: open_dt, open_price, side, sl, tp, maybe exit_dt

A strategy only decides **entries**. It returns open positions, and
`domain.pandas_approach.simulation.simulate_positions` decides how each one
closed. So a strategy never looks at what happens after its entry, and exit
logic is written and tested once.

Look-ahead is the strategy's responsibility: `generate_positions` sees the
whole history, so a signal on bar `i` must only use bars up to `i`.

Writing a strategy as a frozen dataclass gives `parameters()` for free (its
fields), and that is what a backtest records in `run.json`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, is_dataclass
from datetime import date

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position

__all__ = ["TradingStrategy"]


class TradingStrategy(ABC):
    """Turns historical data into open positions."""

    @property
    def name(self) -> str:
        """A label for reports; the class name unless overridden."""
        return type(self).__name__

    def parameters(self) -> dict[str, object]:
        """The settings that define this run of the strategy.

        A dataclass strategy's fields; override for anything else.
        """
        return asdict(self) if is_dataclass(self) else {}

    def split_days(self, data: HistoricalData) -> Iterable[date]:
        """The calendar days the discovery / validation / test split is cut over.

        Every day with a bar, by default. Override when the strategy only
        trades a subset of days -- v28 splits over the days with a usable
        Asia range -- so the boundaries fall where the research put them.
        """
        return data.data["datetime"].dt.date.unique()

    @abstractmethod
    def generate_positions(self, data: HistoricalData) -> list[Position]:
        """Every entry the strategy takes over `data`, as open positions."""
