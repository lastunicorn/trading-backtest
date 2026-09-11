"""Resample a stream of `Bar` objects onto a coarser, fixed-width grid.

Stdlib only -- unlike `domain.frames.resample_ohlc`, which collapses a pandas
frame, this works bar-by-bar on anything iterable (a list, or a generator such
as `ports.mt5_file_access.iter_bars`), so a multi-year stream resamples in
constant memory without ever going through pandas.

    from ports.mt5_file_access import iter_bars
    from tools.resample_bars import resample_bars

    for bar in resample_bars(iter_bars(path)):   # 5-minute bars, the default
        ...

Bars must arrive in chronological order -- the same assumption `iter_bars`
already satisfies -- since a bucket is closed out (and yielded) as soon as a
bar from a later bucket appears; this does not re-sort or buffer the whole
stream.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import datetime

from domain.bar import Bar

__all__ = ["resample_bars"]


def _bucket_start(dt: datetime, interval_minutes: int) -> datetime:
    """Floor `dt` onto the interval grid, anchored at 00:00 of its own day."""
    floored_minute = (dt.minute // interval_minutes) * interval_minutes
    return dt.replace(minute=floored_minute, second=0, microsecond=0)


def _squash(bucket_dt: datetime, bars: list[Bar]) -> Bar:
    """Collapse one bucket's bars into a single OHLC candle."""
    spreads = [bar.spread for bar in bars if bar.spread is not None]

    return Bar(
        dt=bucket_dt,
        open=bars[0].open,
        high=max(bar.high for bar in bars),
        low=min(bar.low for bar in bars),
        close=bars[-1].close,
        tick_volume=sum(bar.tick_volume for bar in bars),
        real_volume=sum(bar.real_volume for bar in bars),
        spread=round(sum(spreads) / len(spreads)) if spreads else None,
    )


def resample_bars(bars: Iterable[Bar], interval_minutes: int) -> Iterator[Bar]:
    """Collapse `bars` onto `interval_minutes`-wide buckets anchored at 00:00.

    OHLC follows the usual rule -- open of the bucket's first bar, high/low
    extremes, close of its last -- tick/real volume sum, spread averages
    (None if no source bar carried one). A bucket is emitted as soon as a bar
    from the next one is seen, plus a final bucket when the stream ends, so
    this is a generator: nothing is buffered beyond the bucket in progress.
    """
    if interval_minutes <= 0:
        raise ValueError(f"interval_minutes must be positive, got {interval_minutes}")

    current_start: datetime | None = None
    current_bars: list[Bar] = []

    for bar in bars:
        bucket_start = _bucket_start(bar.dt, interval_minutes)

        if current_start is not None and bucket_start != current_start:
            yield _squash(current_start, current_bars)
            current_bars = []

        current_start = bucket_start
        current_bars.append(bar)

    if current_bars:
        yield _squash(current_start, current_bars)
