"""`Symbol`: the fixed specification of a tradeable instrument -- its pip size
and tick size -- and nothing else. A `Symbol` doesn't know about bars, prices
observed, or any strategy; it's the constant a strategy consults to convert a
raw price difference into pips (`to_pips`) or to format a price to the
instrument's native precision (`price_decimals`, derived from `tick_size`).

The known instruments are module constants (`EURUSD`, `USDJPY`, ...),
collected by ticker in `SYMBOLS`, which `by_ticker` looks up.

Frozen, like `TradingSession` -- a symbol's specification doesn't
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
from enum import Enum
from functools import cached_property

__all__ = [
    "Symbol",
    "SymbolCategory",
    "EURUSD",
    "GBPUSD",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "USDJPY",
    "XAUUSD",
    "XAGUSD",
    "SYMBOLS",
    "by_ticker",
]


class SymbolCategory(Enum):
    """What kind of instrument a `Symbol` is. Just the two this repo has
    symbols for so far -- extend as new categories show up."""

    FOREX = "Forex"
    COMMODITY = "Commodity"


@dataclass(frozen=True)
class Symbol:
    """A tradeable instrument's fixed specification."""

    name: str
    ticker: str
    pip_size: float
    tick_size: float
    category: SymbolCategory

    def to_pips(self, price_diff: float) -> float:
        """Convert a price-unit difference (e.g. `Bar.range`,
        `Position.risk_amount`) into this symbol's pips."""
        return price_diff / self.pip_size

    @cached_property
    def price_decimals(self) -> int:
        # str(float) switches to scientific notation below 1e-4 (e.g.
        # "1e-05"), so counting characters after "." breaks for tick sizes
        # that small. Decimal(str(x)) parses either form and its exponent
        # gives the decimal place count directly, with no string-splitting.
        return -Decimal(str(self.tick_size)).as_tuple().exponent


EURUSD = Symbol("Euro / U.S. Dollar", "EURUSD", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)
GBPUSD = Symbol("British Pound / U.S. Dollar", "GBPUSD", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)
AUDUSD = Symbol("Australian Dollar / U.S. Dollar", "AUDUSD", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)
NZDUSD = Symbol("New Zealand Dollar / U.S. Dollar", "NZDUSD", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)
USDCAD = Symbol("U.S. Dollar / Canadian Dollar", "USDCAD", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)
USDCHF = Symbol("U.S. Dollar / Swiss Franc", "USDCHF", pip_size=0.0001, tick_size=0.00001, category=SymbolCategory.FOREX)

# JPY pairs quote two decimals fewer than the others -- a pip is the 2nd
# decimal (0.01), not the 4th, and the tradeable tick is the 3rd.
USDJPY = Symbol("U.S. Dollar / Japanese Yen", "USDJPY", pip_size=0.01, tick_size=0.001, category=SymbolCategory.FOREX)

# Metals have no cross-broker-standard "pip" the way FX pairs do -- unlike a
# currency pair's pip, which is fixed by convention, a metal's is effectively
# whatever the quoting broker's price precision implies. These follow the
# common MT5 default (gold quoted to 2 decimals, pip = the 1st of those, tick
# = the 2nd; silver one decimal deeper); adjust to match your actual
# broker/data source if it differs.
XAUUSD = Symbol("Gold / U.S. Dollar", "XAUUSD", pip_size=0.1, tick_size=0.01, category=SymbolCategory.COMMODITY)
XAGUSD = Symbol("Silver / U.S. Dollar", "XAGUSD", pip_size=0.01, tick_size=0.001, category=SymbolCategory.COMMODITY)

# Every known symbol by ticker: what `by_ticker`, config validation and
# `show_symbols.py` see. A new symbol must be added here as well as defined.
SYMBOLS: dict[str, Symbol] = {
    symbol.ticker: symbol
    for symbol in (EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF, USDJPY, XAUUSD, XAGUSD)
}


def by_ticker(ticker: str) -> Symbol:
    """Look up a symbol in `SYMBOLS` by its ticker (case-insensitive)."""
    try:
        return SYMBOLS[ticker.upper()]
    except KeyError:
        raise ValueError(f"unknown symbol ticker {ticker!r}") from None
