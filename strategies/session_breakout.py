"""Session Breakout: the removed `session_breakout_strategy.py`'s rules as a `TradingStrategy`.

    from strategies.session_breakout import SessionBreakout

    positions = SessionBreakout().generate_positions(data)   # M1 bars, any clock

For each calendar day D (a UTC date):

  1. The reference session -- 09:00-18:00 Asia/Tokyo by default, which is
     00:00-09:00 UTC -- sets H and L, wicks included. A day whose range
     exceeds `max_range_pips` is cancelled.
  2. From the session's end on D until its end on D+1, the first bar reaching
     H opens a long at H and the first bar reaching L a short at L. Both can
     trigger on the same day.
  3. Stop: the midpoint of [L, H]. Target: `risk_reward` x that risk.
  4. Still open at the session's end on D+1, it is closed there.

Step 4's exits are the simulator's job; this class emits the entries with
`exit_dt` at the session's end on D+1. The entry is at a level inside the
trigger bar, so by default its positions are `EntryFill.AT_LEVEL` and SL/TP
are checked from the next bar. The script checked them on the trigger bar
itself, settled a bar touching both as ambiguous and charged no costs, so the
parity run sets `check_trigger_bar` true (its positions become
`EntryFill.AT_OPEN`, as if filled at the trigger bar's open), and its
`simulation` is `ambiguity` exclude, `cost.commission_pips` 0:

    python3 backtest.py backtests/session_breakout

Behaviour kept from the script on purpose (the port is trade-for-trade):

- Breakouts are looked for until the session's end on D+1, not until
  midnight as tokyo-session-breakout.md says.
- A day's session bars are only those on UTC date D, so a session crossing
  UTC midnight is cut there, and one ending on D+1 never trades (its
  breakout window is empty).
- The session starts no earlier than 00:00 UTC on D: the script only creates
  day D's session at the first bar dated D.

One departure: a day whose session has H == L is skipped. The script would
open two zero-risk positions there, which a `Position` cannot represent.

The session is set by `session_start`, `session_end` and `session_timezone`
(an IANA name, or "broker" for the broker-server clock). The bars are
converted to UTC internally and positions are emitted on the data's own
clock, so the strategy runs on broker-server (MT5) and UTC (Dukascopy) data
alike.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfoNotFoundError

import numpy as np
import pandas as pd

from domain.broker_clock import timezone_by_name
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import EntryFill, Position, Side
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.pandas_approach.trading_strategy import TradingStrategy
from domain.trading_session import TradingSession

__all__ = ["SessionBreakout"]


@dataclass(frozen=True)
class _SessionDay:
    """One day with a usable reference session: its levels and breakout window."""

    day: date
    high: float
    low: float
    trade_start: int    # first row of the breakout window
    trade_stop: int     # one past its last row
    exit_utc: datetime  # aware; the session's end on the next day


@dataclass(frozen=True)
class SessionBreakout(TradingStrategy):
    session_start: time = time(9, 0)
    session_end: time = time(18, 0)
    session_timezone: str = "Asia/Tokyo"
    max_range_pips: float = 30.0
    risk_reward: float = 1.5
    # The script's rule: SL/TP can hit on the trigger bar itself. For parity, not results.
    check_trigger_bar: bool = False

    def __post_init__(self) -> None:
        if self.risk_reward <= 0:
            raise ValueError(f"risk_reward must be positive, got {self.risk_reward}")
        if self.max_range_pips <= 0:
            raise ValueError(f"max_range_pips must be positive, got {self.max_range_pips}")
        self._reference_session()    # raises on an unknown session_timezone

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        times = data.data["datetime"].to_numpy()
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        positions = []
        for session in self._session_days(data):
            if data.symbol.to_pips(session.high - session.low) > self.max_range_pips:
                continue

            mid = (session.high + session.low) / 2
            exit_dt = session.exit_utc.astimezone(data.timezone).replace(tzinfo=None)
            window = slice(session.trade_start, session.trade_stop)

            for side, level, touched, tag in (
                (Side.LONG, session.high, high[window] >= session.high, "break-high"),
                (Side.SHORT, session.low, low[window] <= session.low, "break-low"),
            ):
                if not touched.any():
                    continue

                row = session.trade_start + int(np.argmax(touched))
                # PendingPosition.for_level's arithmetic, so the levels match the script's bit for bit.
                reward = self.risk_reward * abs(level - mid)
                positions.append(Position(
                    open_dt=pd.Timestamp(times[row]),
                    open_price=level,
                    side=side,
                    sl=mid,
                    tp=level + reward if side == Side.LONG else level - reward,
                    entry_fill=EntryFill.AT_OPEN if self.check_trigger_bar else EntryFill.AT_LEVEL,
                    exit_dt=exit_dt,
                    tag=tag,
                ))

        return positions

    def split_days(self, data: HistoricalData) -> list[date]:
        """Days with a usable session, whatever their range.

        Not filtered by `max_range_pips`, so tuning it doesn't move the split boundaries.
        """
        return [session.day for session in self._session_days(data)]

    def _session_days(self, data: HistoricalData) -> Iterator[_SessionDay]:
        """Each UTC date with bars whose reference session has bars and a positive range."""
        reference_session = self._reference_session()
        utc = shift_timezone(data.data[["datetime"]], UTC, from_tz=data.timezone)["datetime"]
        stamps = utc.to_numpy()
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        def row(at: datetime) -> int:
            """The first row at or after the aware instant `at`."""
            # At the column's own unit: a mismatched one makes numpy convert the whole column on every call.
            instant = np.datetime64(at.astimezone(UTC).replace(tzinfo=None)).astype(stamps.dtype)
            return int(np.searchsorted(stamps, instant, side="left"))

        for day in pd.unique(utc.dt.date):
            session = reference_session.create_session(day)
            midnight = datetime.combine(day, time(0, 0), tzinfo=UTC)
            next_midnight = midnight + timedelta(days=1)

            start = row(max(session.start_dt_utc(), midnight))
            stop = row(min(session.end_dt_utc(), next_midnight))
            if stop <= start:
                continue

            session_high = float(high[start:stop].max())
            session_low = float(low[start:stop].min())
            if not session_high > session_low:
                continue

            exit_utc = reference_session.end_time_utc_on(day + timedelta(days=1))
            yield _SessionDay(
                day=day,
                high=session_high,
                low=session_low,
                trade_start=row(max(session.end_dt_utc(), midnight)),
                trade_stop=row(exit_utc),
                exit_utc=exit_utc,
            )

    def _reference_session(self) -> TradingSession:
        try:
            zone = timezone_by_name(self.session_timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"unknown session_timezone {self.session_timezone!r}") from error
        return TradingSession(
            start_time=self.session_start.replace(tzinfo=zone),
            end_time=self.session_end.replace(tzinfo=zone),
        )
