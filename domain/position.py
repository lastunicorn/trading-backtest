"""The `Position` entity, its resolution `Outcome`, and `PendingPosition` --
the setup a side would enter at before it has actually triggered.

Domain vocabulary alongside `bar.Bar` and `bar_block.BarBlock` -- where those
describe market data, this module describes one side of a trade: a
`PendingPosition` is the price/SL/TP it *would* enter at if triggered,
`materialize()`d into a `Position` -- entry, stop-loss, take-profit, and how
it eventually resolved -- at the moment it actually does. A `Position` always
exists already triggered; under what conditions a strategy decides to
trigger it is that strategy's own concern, not this module's. Likewise, a
risk/reward ratio is a strategy parameter -- `PendingPosition.for_level`
takes it as an argument rather than assuming one.

`risk_value`/`reward_value` are price-unit deltas, not pips -- `Position`
doesn't know a pip size (0.0001 for most FX pairs, 0.01 for JPY pairs, none
at all for other instruments). Converting to pips, and any strategy-specific
text for each `Outcome`, is the caller's job.

Stdlib only, and imports nothing else from `domain/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto

__all__ = ["Outcome", "Position", "PendingPosition"]


class Outcome(Enum):
    """How a `Position` currently stands. `NONE` means still open."""

    NONE = auto()
    TP_HIT = auto()
    SL_HIT = auto()
    AMBIGUOUS = auto()
    FORCE_CLOSED = auto()


@dataclass
class Position:
    """One side of a trade, once triggered."""

    entry_dt: datetime
    entry_price: float

    sl: float
    tp: float

    outcome: Outcome = Outcome.NONE

    resolved_dt: datetime | None = None
    resolved_price: float | None = None

    @property
    def is_resolved(self) -> bool:
        return self.resolved_dt is not None

    @property
    def risk_value(self) -> float:
        return abs(self.entry_price - self.sl)

    @property
    def reward_value(self) -> float:
        return abs(self.tp - self.entry_price)


@dataclass(frozen=True, slots=True)
class PendingPosition:
    """The price, SL and TP one side would enter at if it triggers -- fixed
    before any breakout has happened."""

    price: float
    sl: float
    tp: float

    @classmethod
    def for_level(cls, price: float, sl: float, risk_reward: float) -> "PendingPosition":
        risk = abs(price - sl)
        reward = risk_reward * risk
        tp = price + reward * (1 if price > sl else -1)
        return cls(price=price, sl=sl, tp=tp)

    @classmethod
    def for_level(cls, price: float, sl: float, tp: float) -> "PendingPosition":
        return cls(price=price, sl=sl, tp=tp)

    def open_position(self, entry_dt: datetime) -> Position:
        return Position(entry_dt=entry_dt, entry_price=self.price, sl=self.sl, tp=self.tp)
