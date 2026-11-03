"""MT5 exports as `Bar` objects (the domain entity, `domain.bar_approach.bar.Bar`).

Reading the format is `libs.metatrader_csv`; this module turns its records
into `Bar`s. (Writing is `mt5_frame_reader.write_frame`.) Pure I/O: no cleaning, no resampling, no
strategy logic. Its own code is stdlib only.

    from ports.mt5_file_access import read_bars, iterate_bars

    bars = read_bars("data/eurusd/1min/EURUSD_2020_01.csv")   # list[Bar]
    print(bars[0].dt, bars[0].close)

    for bar in iterate_bars(path):        # streaming, constant memory
        ...

A volume the export leaves blank or doesn't have is 0 on the `Bar`; a missing
spread is None. A headerless 8-column export is read as ending in the spread
(`export_conventions`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from domain.bar_approach.bar import Bar
from libs.metatrader_csv import MetatraderParseError, iterate_records
from ports.mt5_file_access.export_conventions import HEADERLESS_LAYOUTS

__all__ = [
    "Bar",  # re-exported for convenience; canonical import is `from domain.bar_approach.bar import Bar`
    "BarParseError",
    "iterate_bars",
    "read_bars",
]

# A line that could not be turned into a Bar (path, line_no, reason, line).
BarParseError = MetatraderParseError


def iterate_bars(
    path: str,
    *,
    strict: bool = True,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> Iterator[Bar]:
    """Yield each Bar in `path`, one at a time.

    Memory stays flat regardless of file size, so this is the one to use on the
    multi-million-row combined exports.

    strict   -- True raises BarParseError on a malformed line; False skips it.
    on_skip  -- called as (line_no, line, reason) for each skipped line.
    """
    for record in iterate_records(path, strict=strict, on_skip=on_skip, headerless_layouts=HEADERLESS_LAYOUTS):
        yield Bar(
            dt=record.dt,
            open=record.open,
            high=record.high,
            low=record.low,
            close=record.close,
            tick_volume=record.tick_volume or 0,
            real_volume=record.volume or 0,
            spread=record.spread,
        )


def read_bars(
    path: str,
    *,
    strict: bool = True,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> list[Bar]:
    """Read `path` fully into a list of Bars, in file order.

    Convenient for a single monthly export (~31k bars). Prefer iterate_bars() when
    the file could be large.
    """
    return list(iterate_bars(path, strict=strict, on_skip=on_skip))
