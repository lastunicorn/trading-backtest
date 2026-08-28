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
        return self.high - self.low

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open
