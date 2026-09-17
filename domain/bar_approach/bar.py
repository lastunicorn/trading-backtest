"""The `Bar` entity: one OHLC candle, as the rest of the codebase understands it.

This is domain vocabulary, not a file-format detail. A `Bar` knows how to answer
questions about itself (`range`, `is_bullish`) and to project its instant onto a
`date` or a `time`. `ports.mt5_file_access` is one *producer* of `Bar`s -- it
parses MT5 exports into them -- but it does not own the type; anything that reads
or builds candles depends on this module.

Stdlib only (dataclasses + datetime) and imports nothing else from `domain/`, so
`ports/` can depend on it without pulling in pandas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime, time as _time

__all__ = ["Bar"]


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLC candle. Immutable, and cheap enough to hold a month of them."""

    dt: datetime

    open: float
    high: float
    low: float
    close: float

    tick_volume: int = 0
    real_volume: int = 0

    spread: int | None = None

    @property
    def date(self) -> _date:
        return self.dt.date()

    @property
    def time(self) -> _time:
        return self.dt.time()

    @property
    def range(self) -> float:
        """High-low, in price units."""
        return abs(self.high - self.low)

    @property
    def body_range(self) -> float:
        """The absolute difference between the open and close prices."""
        return abs(self.close - self.open)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def midpoint(self) -> float:
        """The average of the high and low prices."""
        return (self.high + self.low) / 2

    def contains(self, price: float) -> bool:
        """Check if the given price is within this bar's high-low range."""
        return self.low <= price <= self.high

    def is_partially_above_or_equal(self, price: float) -> bool:
        """Check if any part of the bar is above or equal to the given price."""
        return self.high >= price

    def is_partially_below_or_equal(self, price: float) -> bool:
        """Check if any part of the bar is below or equal to the given price."""
        return self.low <= price

    def is_completely_above_or_equal(self, price: float) -> bool:
        """Check if the bar's low is above or equal to the given price."""
        return self.low >= price

    def is_completely_below_or_equal(self, price: float) -> bool:
        """Check if the bar's high is below or equal to the given price."""
        return self.high <= price
