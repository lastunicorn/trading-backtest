"""`TradingSessionTemplate`: a trading session's daily time window, and nothing
else -- unlike `tokyo_session.TokyoSession`, a template holds no bars, it just
describes when a session runs.

`start_time` and `end_time` each carry their own `tzinfo` and are independently
sufficient to resolve to UTC -- there is no shared `timezone` field, so a
template's start and end are free to be defined in different zones (e.g. an
Asia-session start paired with a London-session end). Converting a bound to
UTC needs a specific calendar date whenever its zone observes daylight saving,
so that conversion is the `start_time_utc()`/`end_time_utc()` methods, not a
bare property -- there is no single "the UTC start time" for a DST-observing
session, only "the UTC start time on date X" (see `NewYorkSessionTemplate`).

Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date as _date, datetime, time as _time, timedelta
from zoneinfo import ZoneInfo

from domain.trading_session import TradingSession

__all__ = [
    "TradingSessionTemplate",
    "TokyoSessionTemplate",
    "LondonSessionTemplate",
    "NewYorkSessionTemplate",
]


@dataclass(frozen=True)
class TradingSessionTemplate:
    """A trading session's daily window: a start and an end, each a
    timezone-aware local time. Frozen -- a template is a fixed description of
    a session, not something that accumulates state like `TokyoSession` does.
    """

    start_time: _time
    end_time: _time

    def __post_init__(self) -> None:
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("start_time and end_time must be timezone-aware (pass a tzinfo/ZoneInfo on each)")

    def start_time_on(self, date: _date) -> datetime:
        """`start_time` on calendar date `date`, as a timezone-aware `datetime` in its own local time."""
        return datetime.combine(date, self.start_time)

    def end_time_on(self, date: _date) -> datetime:
        """`end_time` on calendar date `date`, as a timezone-aware `datetime` in its own local time."""
        return datetime.combine(date, self.end_time)

    def start_time_utc_on(self, date: _date) -> datetime:
        """`start_time` on calendar date `date`, converted to UTC.

        Takes a date rather than being a bare property because a
        DST-observing zone has no single UTC offset -- only one per date.
        """
        return self.start_time_on(date).astimezone(UTC)

    def end_time_utc_on(self, date: _date) -> datetime:
        """`end_time` on calendar date `date`, converted to UTC. See `start_time_utc_on`."""
        return self.end_time_on(date).astimezone(UTC)

    def create_session(self, date: _date) -> TradingSession:
        """Create a `TradingSession` instance for the given calendar date `date`.

        Compares actual UTC instants (not raw local wall-clock times) to
        decide whether the session wraps past midnight -- with start and end
        potentially in different zones, comparing their local times directly
        wouldn't mean anything.
        """
        start_dt_utc = self.start_time_utc_on(date)
        end_dt_utc = self.end_time_utc_on(date)
        if end_dt_utc <= start_dt_utc:
            end_dt_utc = self.end_time_utc_on(date + timedelta(days=1))

        return TradingSession(start_dt=start_dt_utc, end_dt=end_dt_utc)


@dataclass(frozen=True)
class TokyoSessionTemplate(TradingSessionTemplate):
    """09:00-15:30 Japan Standard Time -- the Tokyo Stock Exchange's opening
    and closing bell times (the TSE close moved from 15:00 to 15:30 in
    November 2024). The TSE actually halts for a lunch break (11:30-12:30),
    so bell-to-bell isn't continuous trading, but `TradingSessionTemplate`
    models one window per day -- this is that window's outer bounds, not the
    rounder 09:00-18:00 sometimes used for the informal FX "Tokyo session".
    """

    start_time: _time = _time(9, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    end_time: _time = _time(15, 30, tzinfo=ZoneInfo("Asia/Tokyo"))


@dataclass(frozen=True)
class LondonSessionTemplate(TradingSessionTemplate):
    """08:00-16:30 Europe/London -- the London Stock Exchange's official
    cash-market bell times, not the rounder 08:00-17:00 sometimes used for
    the informal FX "London session".
    """

    start_time: _time = _time(8, 0, tzinfo=ZoneInfo("Europe/London"))
    end_time: _time = _time(16, 30, tzinfo=ZoneInfo("Europe/London"))


@dataclass(frozen=True)
class NewYorkSessionTemplate(TradingSessionTemplate):
    """09:30-16:00 Eastern Time -- the NYSE's official cash-market bell times,
    not the rounder 08:00-17:00 sometimes used for the informal FX "New York
    session" (which starts 1.5 hours before the NYSE even opens).

    14:30-21:00 UTC under EST, 13:30-20:00 UTC under EDT -- which one applies
    depends on the date, resolved via the IANA tz database rather than a
    hardcoded date range.
    """

    start_time: _time = _time(9, 30, tzinfo=ZoneInfo("America/New_York"))
    end_time: _time = _time(16, 0, tzinfo=ZoneInfo("America/New_York"))
