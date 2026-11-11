"""`Position`: one simulated trade, and `PositionOutcome`: how it ended.

    from domain.backtesting.position import Position, PositionOutcome, Side, positions_to_frame

    position = Position(open_dt=t, open_price=1.1000, side=Side.LONG, sl=1.0980, tp=1.1040)
    position.close(at=t2, price=1.1040, outcome=PositionOutcome.TAKE_PROFIT_HIT)
    frame = positions_to_frame([position])

A strategy creates positions *open* -- entry, SL, TP, how the entry filled
(`entry_fill`) and optionally `exit_dt`, the time it should be cut off if
neither level is hit. Deciding how it closed is the simulator's job, not the
strategy's, which is why `close()` is the only way a position's close fields
change.

`EntryFill` says where in its entry bar a position filled, which decides
whether that bar can hit its SL or TP: at the bar's open the whole bar comes
after the fill, so it can (`AT_OPEN`); at a level inside the bar, OHLC can't
tell whether the bar's extremes came before or after the fill, so it can't
(`AT_LEVEL`, the default).

Prices are raw price units, not pips: a `Position` doesn't know its symbol's
pip size. Converting to pips is the caller's job, via `domain.symbol.Symbol`.

`Side` is re-exported from `domain.backtesting.side` for convenience.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import pandas as pd

from domain.backtesting.side import Side

__all__ = ["FRAME_COLUMNS", "EntryFill", "Position", "PositionOutcome", "Side", "positions_to_frame"]


class PositionOutcome(Enum):
    """How a `Position` stands. `OPEN` means not closed yet."""

    OPEN = "open"
    STOP_LOSS_HIT = "stop-loss-hit"
    TAKE_PROFIT_HIT = "take-profit-hit"
    # Closed at `exit_dt` (a time stop) or by the strategy's own rule.
    MANUAL_CLOSE = "manual-close"
    # Still open when the bars ran out -- not a decision anyone made.
    END_OF_DATA = "end-of-data"
    # One bar touched both SL and TP; which came first is unknowable from OHLC.
    AMBIGUOUS = "ambiguous"


class EntryFill(Enum):
    """Where in its entry bar a position filled."""

    # At a price inside the bar (a stop or limit order): SL/TP are checked from the next bar.
    AT_LEVEL = "at-level"
    # At the bar's open (a market order on a closed signal bar): the entry bar is checked too.
    AT_OPEN = "at-open"


@dataclass(slots=True)
class Position:
    """One trade: opened by a strategy, closed by the simulator."""

    open_dt: datetime
    open_price: float
    side: Side
    sl: float
    tp: float

    entry_fill: EntryFill = EntryFill.AT_LEVEL
    exit_dt: datetime | None = None
    close_dt: datetime | None = None
    close_price: float | None = None
    outcome: PositionOutcome = PositionOutcome.OPEN

    # Free text for the strategy (e.g. "break-high"); a column to group on later.
    tag: str = ""

    def __post_init__(self) -> None:
        if self.side == Side.LONG and not (self.sl < self.open_price < self.tp):
            raise ValueError(
                f"long position needs sl < open_price < tp, "
                f"got sl={self.sl}, open_price={self.open_price}, tp={self.tp}"
            )

        if self.side == Side.SHORT and not (self.tp < self.open_price < self.sl):
            raise ValueError(
                f"short position needs tp < open_price < sl, "
                f"got tp={self.tp}, open_price={self.open_price}, sl={self.sl}"
            )

        if self.exit_dt is not None and self.exit_dt <= self.open_dt:
            raise ValueError(f"exit_dt {self.exit_dt} must be after open_dt {self.open_dt}")

    @property
    def is_closed(self) -> bool:
        return self.outcome != PositionOutcome.OPEN

    def close(self, at: datetime, price: float | None, outcome: PositionOutcome) -> None:
        """Record how the position ended.

        `price` is None only for an `AMBIGUOUS` outcome, which has no honest
        fill price. A position closes once; closing it again raises.
        """
        if self.is_closed:
            raise ValueError(f"position opened at {self.open_dt} is already closed ({self.outcome.value})")

        if outcome == PositionOutcome.OPEN:
            raise ValueError("cannot close a position with outcome OPEN")

        if at < self.open_dt:
            raise ValueError(f"close time {at} is before open_dt {self.open_dt}")

        if (price is None) != (outcome == PositionOutcome.AMBIGUOUS):
            raise ValueError("close price must be None for an AMBIGUOUS outcome, and only then")

        self.close_dt = at
        self.close_price = price
        self.outcome = outcome


# Column order of `positions_to_frame`, and of the positions file built from it.
FRAME_COLUMNS = (
    "open_dt",
    "side",
    "open_price",
    "sl",
    "tp",
    "entry_fill",
    "exit_dt",
    "close_dt",
    "close_price",
    "outcome",
    "tag",
)

_DATETIME_COLUMNS = ("open_dt", "exit_dt", "close_dt")
_PRICE_COLUMNS = ("open_price", "sl", "tp", "close_price")


def positions_to_frame(positions: list[Position]) -> pd.DataFrame:
    """One row per position, columns in `FRAME_COLUMNS` order.

    Enums become their string values; missing datetimes are `NaT`, a missing
    close price `NaN`. Datetimes are `datetime64[us]`. An empty list gives an empty frame with the same
    columns and dtypes, so callers never special-case "no trades".
    """
    frame = pd.DataFrame(
        [
            (
                p.open_dt,
                p.side.value,
                p.open_price,
                p.sl,
                p.tp,
                p.entry_fill.value,
                p.exit_dt,
                p.close_dt,
                p.close_price,
                p.outcome.value,
                p.tag,
            )
            for p in positions
        ],
        columns=list(FRAME_COLUMNS),
    )

    # Pinned to microseconds -- what pandas 3 parses the repo's CSVs into --
    # rather than whatever resolution the input objects happen to infer.
    for column in _DATETIME_COLUMNS:
        frame[column] = pd.to_datetime(frame[column]).astype("datetime64[us]")

    for column in _PRICE_COLUMNS:
        frame[column] = frame[column].astype("float64")

    for column in ("side", "entry_fill", "outcome", "tag"):
        frame[column] = frame[column].astype("str")

    return frame
