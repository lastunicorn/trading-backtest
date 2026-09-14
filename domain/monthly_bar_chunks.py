"""`MonthlyBarChunks`: split a stream of `Bar` into one run per calendar month.

Stdlib only, and works bar-by-bar on anything iterable -- a list or a
generator such as `ports.mt5_file_access.iter_bars` -- so a multi-year stream
splits in constant memory without going through pandas.

    from domain.monthly_bar_chunks import MonthlyBarChunks

    chunks = MonthlyBarChunks(iter_bars(path))
    while chunks.has_more:
        month_bars = list(chunks.iterate())
        ...  # one calendar month's bars, oldest first

Each `iterate()` call yields bars starting from wherever the previous call
left off, up to (not including) the first bar whose calendar month differs
from that run's first bar. That boundary bar is not lost -- it is buffered
and becomes the first bar handed out by the *next* `iterate()` call. The
source is pulled from lazily, one bar at a time, so `iterate()`'s result must
be consumed (fully or until you stop caring) before calling `iterate()`
again -- both draw from the same underlying iterator. `has_more` answers
"would the next `iterate()` yield anything?" without discarding a bar to find
out -- it peeks at most one bar ahead and buffers it, the same buffer
`iterate()` itself uses at a month boundary.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator

from domain.bar import Bar

__all__ = ["MonthlyBarChunks"]


class MonthlyBarChunks:
    """Wrap an `Iterable[Bar]` and hand it out one calendar month at a time."""

    def __init__(self, bars: Iterable[Bar]) -> None:
        self._bars = iter(bars)
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
        """Yield bars up to the next change of calendar month.

        The run's first bar is whichever bar was buffered at the end of the
        previous call, or else the next bar off the source (nothing is
        yielded if the source is already exhausted). Iteration stops --
        without consuming -- at the first later bar whose (year, month)
        differs from the run's first bar; that bar is buffered so the
        following `iterate()` call starts with it.
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

        month = (first.dt.year, first.dt.month)
        yield first

        for bar in self._bars:
            if (bar.dt.year, bar.dt.month) != month:
                self._buffer = bar
                return
            yield bar

        self._is_exhausted = True
