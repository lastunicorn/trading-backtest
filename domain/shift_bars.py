"""Shift a stream of `Bar` objects by a fixed time offset.

Stdlib only, and works bar-by-bar on anything iterable -- a list or a
generator such as `ports.mt5_file_access.iter_bars` -- so a multi-year stream
shifts in constant memory without going through pandas.

    from datetime import timedelta
    from domain.shift_bars import shift_bars

    utc_bars = shift_bars(server_bars, timedelta(hours=-5))
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import replace
from datetime import timedelta

from domain.bar import Bar

__all__ = ["shift_bars"]


def shift_bars(bars: Iterable[Bar], delta: timedelta) -> Iterator[Bar]:
    """Yield each bar in `bars` with `delta` added to its `dt`.

    Only `dt` changes -- OHLC, volumes and spread are passed through as-is.
    `delta` may be negative to shift earlier.
    """
    for bar in bars:
        yield replace(bar, dt=bar.dt + delta)
