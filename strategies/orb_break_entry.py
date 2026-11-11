"""Opening Range Break, Break Entry (doc/strategies/orb-break-entry/orb-break-entry-rules.md), as a `TradingStrategy`.

    from domain.market_data.trading_session import LONDON_SESSION
    from strategies.orb_break_entry import OrbBreakEntry

    positions = OrbBreakEntry().generate_positions(data)                        # M1 bars, any clock
    positions = OrbBreakEntry(session=LONDON_SESSION).generate_positions(data)  # the London open

The opening range, its order window and its time stop are
`strategies.opening_range.OpeningRangeStrategy`'s: by default the range is
09:30-09:45 ET, the orders wait until 11:30 ET and a trade is flat by 16:00 ET.
For each date with a usable range (H, L):

  1. Two stop orders wait in the order window: the first bar opening in it
     that reaches H opens a long at H, the first that reaches L a short at L.
     Each side fills at most once and they don't cancel each other, so a day
     has 0-2 trades; one bar through both levels opens both.
  2. Stop: the range midpoint. Target: `risk_reward` x that risk (2R).
  3. Still open at the session's end (16:00 ET by default), it is closed there.
     `exit_at_session_end` False holds it until its stop or target, or the data's end.

Step 3's exits are the simulator's job; this class emits the entries with
`exit_dt` set. The entry is at a level inside the trigger bar, so its
positions are `EntryFill.AT_LEVEL` and SL/TP are checked from the next bar (it
can't see a stop hit on the trigger bar itself, a slight optimism). Fills are
at the level even when a bar gaps through it.

    python3 backtest.py backtests/orb_break_entry
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from domain.market_data.historical_data import HistoricalData
from domain.backtesting.position import Position, Side
from strategies.opening_range import OpeningRangeStrategy

__all__ = ["OrbBreakEntry"]


@dataclass(frozen=True)
class OrbBreakEntry(OpeningRangeStrategy):
    risk_reward: float = 2.0

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        times = data.data["datetime"].to_numpy()
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        positions = []
        for orb in self._opening_ranges(data):
            window = slice(orb.orders_start, orb.orders_stop)

            for side, level, touched, tag in (
                (Side.LONG, orb.high, high[window] >= orb.high, "break-high"),
                (Side.SHORT, orb.low, low[window] <= orb.low, "break-low"),
            ):
                if not touched.any():
                    continue

                row = orb.orders_start + int(np.argmax(touched))
                reward = self.risk_reward * abs(level - orb.mid)
                positions.append(Position(
                    open_dt=pd.Timestamp(times[row]),
                    open_price=level,
                    side=side,
                    sl=orb.mid,
                    tp=level + reward if side == Side.LONG else level - reward,
                    exit_dt=orb.exit_dt,
                    tag=tag,
                ))

        return positions
