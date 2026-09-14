"""`BarChunks`: split a stream of `Bar` into runs at configurable calendar boundaries.

Stdlib only, and works bar-by-bar on anything iterable -- a list or a
generator such as `ports.mt5_file_access.iter_bars` -- so a multi-year stream
splits in constant memory without going through pandas.

    from domain.bar_chunks import BarChunks

    chunks = BarChunks(iter_bars(path), granularity="monthly")
    while chunks.has_more:
        month_bars = list(chunks.iterate())
        ...  # one calendar month's bars, oldest first

`granularity` is one of:

    "monthly"   -- one run per calendar (year, month)          [default]
    "yearly"    -- one run per calendar year
    "none"      -- no splitting; a single run holds every bar

Each `iterate()` call yields bars starting from wherever the previous call
left off, up to (not including) the first bar whose boundary key differs
from that run's first bar. That boundary bar is not lost -- it is buffered
and becomes the first bar handed out by the *next* `iterate()` call. The
source is pulled from lazily, one bar at a time, so `iterate()`'s result must
be consumed (fully or until you stop caring) before calling `iterate()`
again -- both draw from the same underlying iterator. `has_more` answers
"would the next `iterate()` yield anything?" without discarding a bar to find
out -- it peeks at most one bar ahead and buffers it, the same buffer
`iterate()` itself uses at a boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import datetime
from typing import Literal

from domain.bar import Bar

__all__ = ["BarChunks", "Granularity", "boundary_key"]

Granularity = Literal["monthly", "yearly", "none"]

_BOUNDARY_KEYS: dict[Granularity, Callable[[datetime], object]] = {
    "monthly": lambda dt: (dt.year, dt.month),
    "yearly": lambda dt: (dt.year,),
    "none": lambda dt: None,
}


def boundary_key(dt: datetime, granularity: Granularity) -> object:
    """The chunk `dt` belongs to under `granularity` -- equal for two
    datetimes iff `BarChunks` would place their bars in the same run.
    Anything with `.year`/`.month` attributes works, so a `date` is fine too.
    """
    try:
        key_func = _BOUNDARY_KEYS[granularity]
    except KeyError:
        raise ValueError(
            f"unknown granularity {granularity!r}; expected one of {sorted(_BOUNDARY_KEYS)}"
        ) from None
    return key_func(dt)


class BarChunks:
    """Wrap an `Iterable[Bar]` and hand it out one calendar run at a time."""

    def __init__(self, bars: Iterable[Bar], granularity: Granularity = "monthly") -> None:
        if granularity not in _BOUNDARY_KEYS:
            raise ValueError(
                f"unknown granularity {granularity!r}; expected one of {sorted(_BOUNDARY_KEYS)}"
            )

        self._bars = iter(bars)
        self._boundary_key = _BOUNDARY_KEYS[granularity]
        self._buffer: Bar | None = None
        self._is_exhausted = False

    @property
    def has_more(self) -> bool:
        """True if a further `iterate()` call would yield at least one bar.

        Safe to check any number of times between `iterate()` calls -- if the
        answer isn't already known from a buffered bar or a prior exhausted
        source, this pulls one bar off the source to find out, and buffers it
        rather than discarding it, so it is still the next bar `iterate()`
        yields.
        """
        if self._buffer is not None:
            return True

        if self._is_exhausted:
            return False

        self._buffer = next(self._bars, None)

        if self._buffer is None:
            self._is_exhausted = True
            return False

        return True

    def iterate(self) -> Iterator[Bar]:
        """Yield bars up to the next boundary change.

        The run's first bar is whichever bar was buffered at the end of the
        previous call, or else the next bar off the source (nothing is
        yielded if the source is already exhausted). Iteration stops --
        without consuming -- at the first later bar whose boundary key
        differs from the run's first bar; that bar is buffered so the
        following `iterate()` call starts with it. With granularity "none"
        the key never changes, so this call drains the entire source.
        """
        if self._is_exhausted:
            return

        first = self._buffer
        self._buffer = None

        if first is None:
            first = next(self._bars, None)
            if first is None:
                self._is_exhausted = True
                return

        key = self._boundary_key(first.dt)
        yield first

        for bar in self._bars:
            if self._boundary_key(bar.dt) != key:
                self._buffer = bar
                return
            yield bar

        self._is_exhausted = True
