"""Shift a stream of `Bar` objects from one timezone's wall clock to another.

Stdlib only (`zoneinfo` has been in the standard library since Python 3.9),
and works bar-by-bar on anything iterable -- a list or a generator such as
`ports.mt5_file_access.iter_bars` -- so a multi-year stream shifts in
constant memory without going through pandas.

Each bar's `dt` is naive (no tzinfo), as every `Bar.dt` in this codebase is.
It is treated as a wall-clock reading already in `from_tz`, localized,
converted to `to_tz` (UTC by default), then returned naive again so the
result stays consistent with the rest of the codebase.

Going through a real zone instead of a fixed `timedelta` is the point: a
`ZoneInfo` such as `ZoneInfo("America/New_York")` carries the IANA
database's actual DST transition dates, so the UTC offset applied shifts
from -5h (EST) to -4h (EDT) on the correct day each year automatically,
rather than a hardcoded delta staying wrong for half of the year. A
`datetime.timezone(timedelta(hours=N))` still works as `from_tz`/`to_tz` for
a source that genuinely never observes DST (e.g. a fixed-offset broker
server), which is a plain conversion with no transition to look up.

    from zoneinfo import ZoneInfo
    from domain.shift_bars import shift_bars

    utc_bars = shift_bars(server_bars, ZoneInfo("America/New_York"))
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import timezone, tzinfo

from domain.bar import Bar

__all__ = ["shift_bars"]


def shift_bars(bars: Iterable[Bar], from_tz: tzinfo, to_tz: tzinfo = timezone.utc) -> Iterator[Bar]:
    """Yield each bar in `bars` with `dt` re-expressed in `to_tz`.

    `bar.dt` is assumed naive, holding a wall-clock time in `from_tz`. The
    returned `dt` is naive too (tzinfo stripped after conversion) -- only the
    instant moves, OHLC/volumes/spread pass through unchanged.
    """
    for bar in bars:
        localized = bar.dt.replace(tzinfo=from_tz)
        converted = localized.astimezone(to_tz).replace(tzinfo=None)
        yield replace(bar, dt=converted)
