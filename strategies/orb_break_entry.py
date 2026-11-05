"""Opening Range Break, Break Entry (doc/orb-break-entry.md), as a `TradingStrategy`.

    from strategies.orb_break_entry import OrbBreakEntry

    positions = OrbBreakEntry().generate_positions(data)   # M1 bars, any clock

For each New York date D (the date in `range_start`'s zone):

  1. The opening range -- bars opening in the `range_minutes` (15) from 09:30
     ET, [09:30, 09:45) by default -- sets H and L,
     wicks included. A day without range bars, or with H == L, does not trade.
  2. Two stop orders wait from the range's end until 11:30 ET (`orders_expire`): the
     first bar opening in that window that reaches H opens a long at H, the
     first that reaches L a short at L. Each side fills at most once and they
     don't cancel each other, so a day has 0-2 trades; one bar through both
     levels opens both.
  3. Stop: the range midpoint. Target: `risk_reward` x that risk (2R).
  4. Still open at `exit_at` (16:00 ET, the NYSE close), it is closed there.
     `exit_at` None holds it until its stop or target, or the data's end.

Step 4's exits are the simulator's job; this class emits the entries with
`exit_dt` set. The entry is at a level inside the trigger bar, so the
framework's default `simulation.resolve_from` "next-bar" applies (it can't
see a stop hit on the trigger bar itself, a slight optimism). Fills are at the
level even when a bar gaps through it.

    python3 backtest.py backtests/orb_break_entry

The windows are timezone-aware times (`ZonedTime`). The bars are compared
against them as real instants and the positions are emitted on the data's
own clock, so the strategy runs on broker-server (MT5) and UTC (Dukascopy)
data alike, across daylight-saving changes.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

import numpy as np
import pandas as pd

from domain.broker_clock import timezone_by_name
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.pandas_approach.trading_strategy import TradingStrategy
from domain.sample_size import SampleUnit
from domain.time_window import ZonedTime

__all__ = ["OrbBreakEntry"]

_NEW_YORK = timezone_by_name("America/New_York")

# Any date: the field order is checked on it when the strategy is built, and
# again on every traded date (a pair of zones may only disagree on some dates).
_REFERENCE_DATE = date(2026, 1, 5)


@dataclass(frozen=True)
class _Windows:
    """One date's bounds, as naive UTC instants."""

    range_start: np.datetime64
    range_end: np.datetime64
    orders_expire: np.datetime64
    exit_at: datetime | None    # aware UTC, or no time stop


@dataclass(frozen=True)
class _RangeDay:
    """One date with a usable opening range: its levels and order window."""

    day: date
    high: float
    low: float
    orders_start: int    # first row of the order window
    orders_stop: int     # one past its last row
    exit_at: datetime | None


@dataclass(frozen=True)
class OrbBreakEntry(TradingStrategy):
    range_start: ZonedTime = time(9, 30, tzinfo=_NEW_YORK)
    range_minutes: int = 15                                     # the range's length; the orders start at its end
    orders_expire: ZonedTime = time(11, 30, tzinfo=_NEW_YORK)   # no entry on a bar opening at or after it
    exit_at: ZonedTime | None = time(16, 0, tzinfo=_NEW_YORK)   # flat by; None: no time stop
    risk_reward: float = 2.0

    def __post_init__(self) -> None:
        for name in ("range_start", "orders_expire", "exit_at"):
            bound = getattr(self, name)
            if bound is not None and bound.tzinfo is None:
                raise ValueError(f"{name} must carry a timezone, got {bound}")
        if self.range_minutes <= 0:
            raise ValueError(f"range_minutes must be positive, got {self.range_minutes}")
        if self.risk_reward <= 0:
            raise ValueError(f"risk_reward must be positive, got {self.risk_reward}")
        self._windows_on(_REFERENCE_DATE)    # raises on bounds out of order

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        times = data.data["datetime"].to_numpy()
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        positions = []
        for orb in self._range_days(data):
            mid = (orb.high + orb.low) / 2
            exit_dt = None if orb.exit_at is None else orb.exit_at.astimezone(data.timezone).replace(tzinfo=None)
            window = slice(orb.orders_start, orb.orders_stop)

            for side, level, touched, tag in (
                (Side.LONG, orb.high, high[window] >= orb.high, "break-high"),
                (Side.SHORT, orb.low, low[window] <= orb.low, "break-low"),
            ):
                if not touched.any():
                    continue

                row = orb.orders_start + int(np.argmax(touched))
                reward = self.risk_reward * abs(level - mid)
                positions.append(Position(
                    open_dt=pd.Timestamp(times[row]),
                    open_price=level,
                    side=side,
                    sl=mid,
                    tp=level + reward if side == Side.LONG else level - reward,
                    exit_dt=exit_dt,
                    tag=tag,
                ))

        return positions

    def split_days(self, data: HistoricalData) -> list[date]:
        """Dates with a usable opening range, traded or not."""
        return [orb.day for orb in self._range_days(data)]

    def _range_days(self, data: HistoricalData) -> Iterator[_RangeDay]:
        """Each date whose opening range has bars and a positive range."""
        self._check_bar_size(data)
        stamps = shift_timezone(data.data[["datetime"]], UTC, from_tz=data.timezone)["datetime"].to_numpy()
        local = shift_timezone(data.data[["datetime"]], self.range_start.tzinfo, from_tz=data.timezone)["datetime"]
        high = data.data["high"].to_numpy()
        low = data.data["low"].to_numpy()

        def row(at: np.datetime64) -> int:
            """The first row at or after the naive UTC instant `at`."""
            # At the column's own unit: a mismatched one makes numpy convert the whole column on every call.
            return int(np.searchsorted(stamps, at.astype(stamps.dtype), side="left"))

        for day in pd.unique(local.dt.date):
            windows = self._windows_on(day)
            start, stop = row(windows.range_start), row(windows.range_end)
            if stop <= start:
                continue

            range_high = float(high[start:stop].max())
            range_low = float(low[start:stop].min())
            if not range_high > range_low:
                continue

            yield _RangeDay(
                day=day,
                high=range_high,
                low=range_low,
                orders_start=stop,
                orders_stop=row(windows.orders_expire),
                exit_at=windows.exit_at,
            )

    def _windows_on(self, day: date) -> _Windows:
        """`day`'s bounds, checked to be in order: range end (range_start + range_minutes) <= orders_expire < exit_at."""
        def utc(bound: time) -> datetime:
            return datetime.combine(day, bound).astimezone(UTC)

        local_start = datetime.combine(day, self.range_start)
        range_start = local_start.astimezone(UTC)
        range_end = (local_start + timedelta(minutes=self.range_minutes)).astimezone(UTC)    # wall-clock minutes
        orders_expire = utc(self.orders_expire)
        exit_at = None if self.exit_at is None else utc(self.exit_at)

        if not range_end <= orders_expire:
            raise ValueError(f"the range ({self.range_minutes} minutes from {self.range_start}) must end by "
                             f"orders_expire {self.orders_expire} on {day}")
        if exit_at is not None and not orders_expire < exit_at:
            raise ValueError(f"exit_at {self.exit_at} must be after orders_expire {self.orders_expire} on {day}")

        def naive(instant: datetime) -> np.datetime64:
            return np.datetime64(instant.replace(tzinfo=None))

        return _Windows(naive(range_start), naive(range_end), naive(orders_expire), exit_at)

    def _check_bar_size(self, data: HistoricalData) -> None:
        """Minute bars that tile the opening range, so no bar straddles its end."""
        windows = self._windows_on(_REFERENCE_DATE)
        range_minutes = (windows.range_end - windows.range_start) // np.timedelta64(1, "m")
        if data.timeframe.unit != SampleUnit.Minute or range_minutes % data.timeframe.amount:
            raise ValueError(f"OrbBreakEntry needs minute bars dividing its {range_minutes}-minute "
                             f"opening range, got {data.timeframe}")
