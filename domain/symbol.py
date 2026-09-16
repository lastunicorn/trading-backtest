"""`Symbol`: the fixed specification of a tradeable instrument -- its pip size
and tick size -- and nothing else. A `Symbol` doesn't know about bars, prices
observed, or any strategy; it's the constant a strategy consults to convert a
raw price difference into pips (`pip_size`) or to format a price to the
instrument's native precision (`price_decimals`, derived from `tick_size`).

Frozen, like `TradingSessionTemplate` -- a symbol's specification doesn't
change once defined. `price_decimals` is a `cached_property` rather than a
plain `property`: it's derived from `tick_size` via `Decimal`, which is
cheap but pointless to redo on every format call, and `cached_property`
writes into the instance's own `__dict__`, bypassing the frozen dataclass's
`__setattr__`, so the caching works despite the class being frozen.

Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import cached_property

__all__ = ["Symbol", "EurUsd"]


@dataclass(frozen=True)
class Symbol:
    """A tradeable instrument's fixed specification."""

    name: str
    ticker: str
    pip_size: float
    tick_size: float

    @cached_property
    def price_decimals(self) -> int:
        # str(float) switches to scientific notation below 1e-4 (e.g.
        # "1e-05"), so counting characters after "." breaks for tick sizes
        # that small. Decimal(str(x)) parses either form and its exponent
        # gives the decimal place count directly, with no string-splitting.
        return -Decimal(str(self.tick_size)).as_tuple().exponent


class EurUsd(Symbol):
    def __init__(self) -> None:
        super().__init__(
            name="Euro / U.S. Dollar",
            ticker="EURUSD",
            pip_size=0.0001,
            tick_size=0.00001,
        )
