"""Opening Range Break, Retest Entry (doc/strategies/orb-retest-entry/orb-retest-entry-rules.md), as a `TradingStrategy`.

    from domain.trading_session import LONDON_SESSION
    from strategies.orb_retest_entry import OrbRetestEntry

    positions = OrbRetestEntry().generate_positions(data)                        # M1 bars, any clock
    positions = OrbRetestEntry(session=LONDON_SESSION).generate_positions(data)  # the London open

The opening range, its order window and its time stop are
`strategies.opening_range.OpeningRangeStrategy`'s: by default the range is
09:30-09:45 ET, the orders wait until 11:30 ET and a trade is flat by 16:00 ET.
For each date with a usable range (H, L, midpoint M):

  1. The break is the first bar opening in the order window that reaches H
     (upwards) or L (downwards). A bar reaching both is ambiguous and the day
     is skipped.
  2. The break places a limit order at M: a long after an upside break, a
     short after a downside one. From the bar after the break until the
     window's end, the first bar reaching M fills it at M. So a day has 0-1 trades.
  3. Stop: the other side of the range (L for the long, H for the short), half
     the range away. Target: `risk_reward` x that risk (3R) beyond M.
  4. Still open at the session's end (16:00 ET by default), it is closed there.
     `exit_at_session_end` False holds it until its stop or target, or the data's end.

A break the other way before the fill can't happen: any bar reaching the far
side passes M first, so it fills the limit (and can stop it out in the same bar).

Step 4's exits are the simulator's job; this class emits the entries with
`exit_dt` set. The break bar can't fill the order, since OHLC can't say whether
it reached M before or after the break. The fill is at a level inside its bar,
so its positions are `EntryFill.AT_LEVEL` and SL/TP are checked from the next
bar. That makes it optimistic: price reaches M before the stop beyond it, so a
fill bar that also reached the stop was stopped out, but the simulator doesn't
see it. Fills are at M even when a bar gaps through it, where a real limit
would fill at the better open.

    python3 backtest.py backtests/orb_retest_entry
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.backtesting.position import Position, Side
from strategies.opening_range import OpeningRangeStrategy

__all__ = ["OrbRetestEntry"]


@dataclass(frozen=True)
class OrbRetestEntry(OpeningRangeStrategy):
    risk_reward: float = 3.0

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        times = data.data["datetime"].to_numpy()
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        positions = []
        for orb in self._opening_ranges(data):
            window = slice(orb.orders_start, orb.orders_stop)
            broke_up = high[window] >= orb.high
            broke_down = low[window] <= orb.low
            broke = broke_up | broke_down
            if not broke.any():
                continue

            offset = int(np.argmax(broke))
            if broke_up[offset] and broke_down[offset]:
                continue    # one bar through both sides: which broke first is unknowable

            # The limit waits from the bar after the break.
            after = slice(orb.orders_start + offset + 1, orb.orders_stop)
            if broke_up[offset]:
                side, sl, retested, tag = Side.LONG, orb.low, low[after] <= orb.mid, "retest-high"
            else:
                side, sl, retested, tag = Side.SHORT, orb.high, high[after] >= orb.mid, "retest-low"
            if not retested.any():
                continue

            row = after.start + int(np.argmax(retested))
            reward = self.risk_reward * abs(orb.mid - sl)
            positions.append(Position(
                open_dt=pd.Timestamp(times[row]),
                open_price=orb.mid,
                side=side,
                sl=sl,
                tp=orb.mid + reward if side == Side.LONG else orb.mid - reward,
                exit_dt=orb.exit_dt,
                tag=tag,
            ))

        return positions
