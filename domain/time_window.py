"""`TimeWindow`: a daily time-of-day window, each bound optional and in its own timezone.

    from datetime import datetime, time
    from zoneinfo import ZoneInfo
    from domain.broker_clock import BROKER_SERVER_TZ
    from domain.time_window import TimeWindow

    london = ZoneInfo("Europe/London")
    window = TimeWindow(time(8, 0, tzinfo=london), time(16, 0, tzinfo=london))
    window.contains(datetime(2026, 1, 5, 12, 0, tzinfo=BROKER_SERVER_TZ))   # True: 10:00 London

A bound is a timezone-aware `datetime.time`, as in
`domain.trading_session_template`: 08:00 London is a different instant in
winter and summer, so a window is resolved against each instant's own date,
never through a fixed offset. `start` is inclusive, `end` exclusive.

Either bound may be None:

  - both set: [start, end) each day. An `end` at or before `start` wraps past
    midnight (22:00-02:00), so `start == end` in one zone is a full day.
    The bounds may be in different zones (an Asia start with a London end).
  - only `start`: from `start` to midnight in `start`'s zone.
  - only `end`: from midnight to `end` in `end`'s zone.
  - neither: every instant.

`ZonedTime` is the type to annotate a strategy field holding such a bound:
`backtest.py` reads it from a config as "HH:MM <zone>" (and a plain `time`
field as "HH:MM", on the data's clock), so neither can be written as the other.

Stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Annotated

__all__ = ["TimeWindow", "ZonedTime"]

# A timezone-aware `datetime.time`. At runtime it is just `time`; the marker is
# for code that reads type hints (`typing.get_type_hints(..., include_extras=True)`).
ZonedTime = Annotated[time, "timezone-aware"]


@dataclass(frozen=True)
class TimeWindow:
    """[start, end) each day; a None bound is open. Bounds must be timezone-aware."""

    start: time | None = None
    end: time | None = None

    def __post_init__(self) -> None:
        for name, bound in (("start", self.start), ("end", self.end)):
            if bound is not None and bound.tzinfo is None:
                raise ValueError(f"TimeWindow {name} {bound} has no timezone; attach a tzinfo")

    def contains(self, instant: datetime) -> bool:
        """Whether the timezone-aware `instant` falls inside the window."""
        if instant.tzinfo is None:
            raise ValueError(f"TimeWindow.contains needs a timezone-aware datetime, got {instant}")

        if self.start is not None and self.end is not None:
            # The window containing `instant`, if any, opened on its date in
            # start's zone or, when it wraps past midnight, the day before.
            day = instant.astimezone(self.start.tzinfo).date()
            return any(self._opens_on(d) <= instant < self._closes_after(d) for d in (day, day - timedelta(days=1)))
        
        if self.start is not None:
            return instant.astimezone(self.start.tzinfo).time() >= self.start.replace(tzinfo=None)
        
        if self.end is not None:
            return instant.astimezone(self.end.tzinfo).time() < self.end.replace(tzinfo=None)
        
        return True

    def _opens_on(self, day: date) -> datetime:
        return datetime.combine(day, self.start)

    def _closes_after(self, day: date) -> datetime:
        """The first `end` after the window opening on `day`."""
        close = datetime.combine(day, self.end)
        return close if close > self._opens_on(day) else datetime.combine(day + timedelta(days=1), self.end)
