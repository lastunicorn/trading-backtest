"""`TradingSessionTemplate`: a trading session's daily time window, and nothing
else -- unlike `tokyo_session.TokyoSession`, a template holds no bars, it just
describes when a session runs.

`start_time`/`end_time` are naive local wall-clock bounds; `timezone` is the
real IANA zone that gives them meaning. Converting those bounds to UTC needs a
specific calendar date whenever `timezone` observes daylight saving, so that
conversion is the `start_time_utc()`/`end_time_utc()` methods, not a bare
property -- there is no single "the UTC start time" for a DST-observing
session, only "the UTC start time on date X" (see `NewYorkSessionTemplate`).

Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime, time as _time, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

from trading_session import TradingSession

__all__ = [
    "TradingSessionTemplate",
    "TokyoSessionTemplate",
    "LondonSessionTemplate",
    "NewYorkSessionTemplate",
]

_JST = timezone(timedelta(hours=9))  # fixed offset: Japan has not observed DST since 1951


@dataclass(frozen=True)
class TradingSessionTemplate:
    """A trading session's daily window: local start/end plus the zone that
    defines it. Frozen -- a template is a fixed description of a session,
    not something that accumulates state like `TokyoSession` does.
    """

    start_time: _time
    end_time: _time
    timezone: tzinfo

    def start_time_on(self, date: _date) -> datetime:
        """`start_time` on calendar date `on`, as a timezone-aware `datetime` in the session's local time."""
        return datetime.combine(date, self.start_time, tzinfo=self.timezone)

    def end_time_on(self, date: _date) -> datetime:
        """`end_time` on calendar date `on`, as a timezone-aware `datetime` in the session's local time."""
        return datetime.combine(date, self.end_time, tzinfo=self.timezone)

    def start_time_utc_on(self, date: _date) -> datetime:
        """`start_time` on calendar date `on`, converted to UTC.

        Takes a date rather than being a bare property because a
        DST-observing `timezone` has no single UTC offset -- only one per date.
        """
        return datetime.combine(date, self.start_time, tzinfo=self.timezone).astimezone(UTC)

    def end_time_utc_on(self, date: _date) -> datetime:
        """`end_time` on calendar date `on`, converted to UTC. See `start_time_utc`."""
        return datetime.combine(date, self.end_time, tzinfo=self.timezone).astimezone(UTC)

    def create_session(self, date: _date) -> TradingSession:
        """Create a `TradingSession` instance for the given calendar date `on`."""
        start_dt_utc = self.start_time_on(date)
        end_dt_utc = self.end_time_on(date) if self.end_time >= self.start_time else self.end_time_on(date + timedelta(days=1))

        return TradingSession(start_dt=start_dt_utc, end_dt=end_dt_utc)


@dataclass(frozen=True)
class TokyoSessionTemplate(TradingSessionTemplate):
    """09:00-15:30 Japan Standard Time -- the Tokyo Stock Exchange's opening
    and closing bell times (the TSE close moved from 15:00 to 15:30 in
    November 2024). The TSE actually halts for a lunch break (11:30-12:30),
    so bell-to-bell isn't continuous trading, but `TradingSessionTemplate`
    models one window per day -- this is that window's outer bounds, not the
    rounder 09:00-18:00 sometimes used for the informal FX "Tokyo session".

    JST is a fixed UTC+9 year-round, so -- unlike the base class -- `start_time`
    and `end_time` here carry that offset directly and stay meaningful without
    a date. (A `zoneinfo.ZoneInfo` would *not* work for this: attached to a
    bare `time` with no date, `ZoneInfo.utcoffset()` always resolves to `None`,
    even for a zone that never observes DST. `timezone` itself still uses the
    real `ZoneInfo`, since `start_time_utc`/`end_time_utc` always combine it
    with a date.)
    """

    start_time: _time = _time(9, 0, tzinfo=_JST)
    end_time: _time = _time(15, 30, tzinfo=_JST)
    timezone: tzinfo = ZoneInfo("Asia/Tokyo")


@dataclass(frozen=True)
class LondonSessionTemplate(TradingSessionTemplate):
    """08:00-16:30 Europe/London -- the London Stock Exchange's official
    cash-market bell times, not the rounder 08:00-17:00 sometimes used for
    the informal FX "London session".

    Like New York, London observes DST (GMT vs. BST), so `start_time`/`end_time`
    stay naive local time -- no fixed offset is correct year-round -- and
    `start_time_utc()`/`end_time_utc()` need a date to resolve which one applies.
    """

    start_time: _time = _time(8, 0)
    end_time: _time = _time(16, 30)
    timezone: tzinfo = ZoneInfo("Europe/London")


@dataclass(frozen=True)
class NewYorkSessionTemplate(TradingSessionTemplate):
    """09:30-16:00 Eastern Time -- the NYSE's official cash-market bell times,
    not the rounder 08:00-17:00 sometimes used for the informal FX "New York
    session" (which starts 1.5 hours before the NYSE even opens).

    14:30-21:00 UTC under EST, 13:30-20:00 UTC under EDT. Which one applies
    depends on the date, so `start_time`/`end_time` stay naive local time here
    (no fixed offset would be correct year-round); call `start_time_utc()`/
    `end_time_utc()` with a specific date to get the right one -- `timezone`
    resolves EST vs. EDT via the IANA tz database rather than a hardcoded
    date range.
    """

    start_time: _time = _time(9, 30)
    end_time: _time = _time(16, 0)
    timezone: tzinfo = ZoneInfo("America/New_York")
