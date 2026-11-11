"""`OpeningRangeStrategy`: a session's opening range, the base of the Opening Range Break strategies.

    @dataclass(frozen=True)
    class MyOrbEntry(OpeningRangeStrategy):
        def generate_positions(self, data: HistoricalData) -> list[Position]:
            for orb in self._opening_ranges(data):
                ...   # orb.high, orb.low, orb.mid; order window rows [orb.orders_start, orb.orders_stop); orb.exit_dt

The opening is a `TradingSession`'s (`session`, `NEW_YORK_SESSION` by
default: 09:30-16:00 ET, the NYSE bells). For each date D in the zone of the
session's start:

  - The opening range is the bars opening in the `opening_range_minutes` (15)
    from the session's start, [09:30, 09:45) ET by default. Their high and low,
    wicks included, are H and L. A day without range bars, or with H == L, has
    no usable range and doesn't trade.
  - The order window runs from the range's end until `order_expiry_minutes`
    (120) after the session's start, 11:30 ET by default: no entry on a bar
    opening at or after it.
  - With `exit_at_session_end`, a trade must be flat by the session's end (16:00
    ET by default), its `exit_dt`. False leaves it to its stop or target, or the
    data's end.

Which orders wait in the window, at which levels, is each subclass's
`generate_positions`: `OrbBreakEntry` (stop orders at H and L) and
`OrbRetestEntry` (a limit at the midpoint after a break). `risk_reward` is
their target distance over their stop distance; each sets its own default.

The session's bounds are timezone-aware times. The bars are compared
against them as real instants and the positions are emitted on the data's
own clock, so the strategies run on broker-server (MT5) and UTC (Dukascopy)
data alike, across daylight-saving changes. The bars must be minutes dividing
the opening range, so that no bar straddles its end.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd

from domain.market_data.historical_data import HistoricalData
from domain.market_data.shift_timezone import shift_timezone
from domain.backtesting.trading_strategy import TradingStrategy
from domain.market_data.sample_size import SampleUnit
from domain.market_data.trading_session import NEW_YORK_SESSION, TradingSession

__all__ = ["OpeningRange", "OpeningRangeStrategy"]

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
class OpeningRange:
    """One date with a usable opening range: its levels and order window."""

    day: date
    high: float
    low: float
    orders_start: int             # first row of the order window
    orders_stop: int              # one past its last row
    exit_dt: datetime | None      # on the data's clock (naive), or no time stop

    @property
    def mid(self) -> float:
        return (self.high + self.low) / 2


@dataclass(frozen=True)
class OpeningRangeStrategy(TradingStrategy):
    session: TradingSession = NEW_YORK_SESSION   # the range starts at its start
    opening_range_minutes: int = 15              # the range's length; the orders start at its end
    order_expiry_minutes: int = 120              # from the session's start: no entry on a bar opening at or after it
    exit_at_session_end: bool = True             # flat by the session's end; False: no time stop
    risk_reward: float = 2.0                     # target distance / stop distance

    def __post_init__(self) -> None:
        for name in ("opening_range_minutes", "order_expiry_minutes"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive, got {getattr(self, name)}")
        if self.risk_reward <= 0:
            raise ValueError(f"risk_reward must be positive, got {self.risk_reward}")
        self._windows_on(_REFERENCE_DATE)    # raises on bounds out of order

    def split_days(self, data: HistoricalData) -> list[date]:
        """Dates with a usable opening range, traded or not."""
        return [orb.day for orb in self._opening_ranges(data)]

    def _opening_ranges(self, data: HistoricalData) -> Iterator[OpeningRange]:
        """Each date whose opening range has bars and a positive range."""
        self._check_bar_size(data)
        stamps = shift_timezone(data.data[["datetime"]], UTC, from_tz=data.timezone)["datetime"].to_numpy()
        local = shift_timezone(data.data[["datetime"]], self.session.start_time.tzinfo,
                               from_tz=data.timezone)["datetime"]
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

            exit_at = windows.exit_at
            yield OpeningRange(
                day=day,
                high=range_high,
                low=range_low,
                orders_start=stop,
                orders_stop=row(windows.orders_expire),
                exit_dt=None if exit_at is None else exit_at.astimezone(data.timezone).replace(tzinfo=None),
            )

    def _windows_on(self, day: date) -> _Windows:
        """`day`'s bounds, checked to be in order: range end <= orders expiry < session end.

        The range end and the orders' expiry are wall-clock minutes from the
        session's start; the session's end is its first after that start.
        """
        local_start = self.session.start_time_on(day)
        range_end = (local_start + timedelta(minutes=self.opening_range_minutes)).astimezone(UTC)
        orders_expire = (local_start + timedelta(minutes=self.order_expiry_minutes)).astimezone(UTC)
        session_end = self.session.create_session(day).end_dt

        if not range_end <= orders_expire:
            raise ValueError(f"the range ({self.opening_range_minutes} minutes) must end by the orders' expiry "
                             f"({self.order_expiry_minutes} minutes) after the {self._session_label} start on {day}")
        if not orders_expire < session_end:
            raise ValueError(f"order_expiry_minutes {self.order_expiry_minutes} must expire the orders "
                             f"before the {self._session_label} end on {day}")

        def naive(instant: datetime) -> np.datetime64:
            return np.datetime64(instant.replace(tzinfo=None))

        return _Windows(naive(local_start.astimezone(UTC)), naive(range_end), naive(orders_expire),
                        session_end if self.exit_at_session_end else None)

    @property
    def _session_label(self) -> str:
        return f"{self.session.name} session" if self.session.name else "session"

    def _check_bar_size(self, data: HistoricalData) -> None:
        """Minute bars that tile the opening range, so no bar straddles its end."""
        windows = self._windows_on(_REFERENCE_DATE)
        range_minutes = (windows.range_end - windows.range_start) // np.timedelta64(1, "m")
        if data.timeframe.unit != SampleUnit.Minute or range_minutes % data.timeframe.amount:
            raise ValueError(f"{self.name} needs minute bars dividing its {range_minutes}-minute "
                             f"opening range, got {data.timeframe}")
