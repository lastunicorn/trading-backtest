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

from domain.bar import Bar

__all__ = ["Outcome", "Position", "PendingPosition"]


class Outcome(Enum):
    """How a `Position` currently stands. `NONE` means still open."""

    NONE = auto()
    TP_HIT = auto()
    SL_HIT = auto()
    AMBIGUOUS = auto()
    FORCE_CLOSED = auto()


@dataclass(slots=True)
class Position:
    """One side of a trade, once triggered."""

    open_dt: datetime
    open_price: float

    sl: float
    tp: float

    outcome: Outcome = Outcome.NONE

    close_dt: datetime | None = None
    close_price: float | None = None

    @property
    def is_closed(self) -> bool:
        return self.close_dt is not None

    @property
    def risk_amount(self) -> float:
        return abs(self.open_price - self.sl)

    @property
    def reward_amount(self) -> float:
        return abs(self.tp - self.open_price)

    @property
    def is_long(self) -> bool:
        return self.tp > self.open_price

    @property
    def is_short(self) -> bool:
        return self.tp < self.open_price

    def close(self, at: datetime) -> None:
        """Force-close the position -- no SL/TP hit, just cut off at `at`."""
        self.outcome = Outcome.FORCE_CLOSED
        self.close_dt = at

    def close_by_sl(self, at: datetime) -> None:
        """Force-close the position due to SL being hit."""
        self.outcome = Outcome.SL_HIT
        self.close_dt = at
        self.close_price = self.sl

    def close_by_tp(self, at: datetime) -> None:
        """Force-close the position due to TP being hit."""
        self.outcome = Outcome.TP_HIT
        self.close_dt = at
        self.close_price = self.tp

    def close_ambiguous(self, at: datetime) -> None:
        """Force-close the position due to both SL and TP being hit in the same bar."""
        self.outcome = Outcome.AMBIGUOUS
        self.close_dt = at
        self.close_price = None

    def hit(self, bar: Bar) -> bool:
        """Update this position if `bar`'s range touches its SL and/or TP."""
        if self.is_long:
            hit_tp = bar.is_partially_above_or_equal(self.tp)
            hit_sl = bar.is_partially_below_or_equal(self.sl)
        else:
            hit_tp = bar.is_partially_below_or_equal(self.tp)
            hit_sl = bar.is_partially_above_or_equal(self.sl)

        if hit_tp and hit_sl:
            self.close_ambiguous(bar.dt)
        elif hit_tp:
            self.close_by_tp(bar.dt)
        elif hit_sl:
            self.close_by_sl(bar.dt)

        return hit_tp or hit_sl


@dataclass(frozen=True, slots=True)
class PendingPosition:
    """The price, SL and TP one side would enter at if it triggers -- fixed
    before any breakout has happened."""

    price: float
    sl: float
    tp: float

    @property
    def is_long(self) -> bool:
        return self.tp > self.price

    @property
    def is_short(self) -> bool:
        return self.tp < self.price

    @classmethod
    def for_level(cls, price: float, sl: float, risk_reward: float) -> "PendingPosition":
        risk = abs(price - sl)
        reward = risk_reward * risk
        tp = price + reward * (1 if price > sl else -1)

        return cls(price=price, sl=sl, tp=tp)

    def try_open_position(self, bar: Bar) -> Position | None:
        """Check if this pending position would be triggered by `bar`."""
        hit = self._is_hit(bar)

        if hit:
            return Position(
                open_dt=bar.dt,
                open_price=self.price,
                sl=self.sl,
                tp=self.tp)

        return None

    def simulate_open_position(self, bar: Bar) -> bool:
        """Check if this pending position would be triggered by `bar`."""
        return self._is_hit(bar)

    def _is_hit(self, bar: Bar) -> bool:
        """Check if this pending position would be triggered by `bar`."""
        if self.is_long:
            return bar.is_partially_above_or_equal(self.price)
        else:
            return bar.is_partially_below_or_equal(self.price)