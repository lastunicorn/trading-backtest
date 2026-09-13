"""`BarBlock`: many bars folded into one open/high/low/close span.

Domain vocabulary alongside `bar.Bar` -- where a `Bar` is one candle, a
`BarBlock` is many candles collapsed into their aggregate OHLC as they arrive,
one bar at a time via `add()`. It starts empty: `day` is `None` and the OHLC
fields are meaningless until the first bar lands.

    from domain.bar_block import BarBlock

    block = BarBlock()
    for bar in bars:
        block.add(bar)
    block.day, block.range, block.mid

Stdlib only, and imports only `bar.Bar` from `domain/`, so it stays as
dependency-free as `Bar` itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, datetime

from domain.bar import Bar

__all__ = ["BarBlock"]


@dataclass
class BarBlock:
    """Bars folded into one OHLC span. Empty until the first `add()`."""

    first_dt: datetime | None = None

    open_value: float | None = None
    open_dt: datetime | None = None

    close_value: float | None = None
    close_dt: datetime | None = None

    high_value: float = float("-inf")
    high_dt: datetime | None = None

    low_value: float = float("inf")
    low_dt: datetime | None = None

    bar_count: int = 0

    @property
    def day(self) -> _date | None:
        """The date of the first bar ever added, or None if the block is empty."""
        return self.first_dt.date() if self.first_dt is not None else None

    def add(self, bar: Bar) -> None:
        """Fold one more bar into the block.

        Open/close track the earliest/latest `dt` seen rather than arrival
        order, so bars need not arrive sorted -- except `day`, which is fixed
        to whichever bar `add()` sees first.
        """
        if self.first_dt is None:
            self.first_dt = bar.dt

        if self.open_dt is None or bar.dt < self.open_dt:
            self.open_value = bar.open
            self.open_dt = bar.dt

        if self.close_dt is None or bar.dt > self.close_dt:
            self.close_value = bar.close
            self.close_dt = bar.dt

        if bar.high > self.high_value:
            self.high_value = bar.high
            self.high_dt = bar.dt

        if bar.low < self.low_value:
            self.low_value = bar.low
            self.low_dt = bar.dt

        self.bar_count += 1

    @property
    def range(self) -> float:
        """High-low, in price units."""
        return self.high_value - self.low_value

    @property
    def mid(self) -> float:
        return (self.high_value + self.low_value) / 2
