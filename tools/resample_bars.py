"""Resample a stream of `Bar` objects onto a coarser grid.

Stdlib only -- unlike `domain.frames.resample_ohlc`, which collapses a pandas
frame, this works bar-by-bar on anything iterable (a list, or a generator such
as `ports.mt5_file_access.iter_bars`), so a multi-year stream resamples in
constant memory without ever going through pandas.

    from ports.mt5_file_access import iter_bars
    from tools.resample_bars import resample_bars

    for bar in resample_bars(iter_bars(path), "5m"):
        ...

Bars must arrive in chronological order -- the same assumption `iter_bars`
already satisfies -- since a bucket is closed out (and yielded) as soon as a
bar from a later bucket appears; this does not re-sort or buffer the whole
stream.

`interval` is an integer amount plus a case-sensitive unit letter, each with
its own anchor -- deliberately not uniform (see `resample_bars` for why):

    5m, 30m   minutes  -- grid resets at 00:00 of each bar's own day
    1h, 4h    hours    -- same, grid resets at 00:00 of each bar's own day
    1d, 7d    days     -- grid anchored to the first bar seen in the stream
    1w, 2w    weeks    -- grid anchored to Monday, fixed regardless of input
    1M, 3M    months   -- grid anchored to the first bar's calendar month
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator
from datetime import date as _date, datetime, timedelta

from domain.bar import Bar

__all__ = ["resample_bars"]

_INTERVAL_RE = re.compile(r"(\d+)([mhdwM])")

_MINUTES_PER_UNIT = {"m": 1, "h": 60}

_MIDNIGHT = datetime.min.time()

# Fixed reference for weeks only -- the Monday on or before the Unix epoch.
# m/h reset per bar-day and d/M anchor to the stream's own first bar, so this
# is the one unit that needs a fixed point of its own to floor multi-week
# spans (2w, 3w, ...) against; a single week is just "Monday of this bar's
# week" and would not need it.
_EPOCH = _date(1970, 1, 1)
_WEEK_EPOCH = _EPOCH - timedelta(days=_EPOCH.weekday())


def _parse_interval(interval: str) -> tuple[int, str]:
    match = _INTERVAL_RE.fullmatch(interval)

    if match is None:
        raise ValueError(
            f"invalid interval {interval!r}; expected an integer amount plus "
            "a unit letter (m/h/d/w/M, case-sensitive), e.g. '5m', '4h', "
            "'7d', '2w', '3M'"
        )

    amount = int(match.group(1))

    if amount <= 0:
        raise ValueError(f"interval amount must be positive, got {interval!r}")

    return amount, match.group(2)


def _bucket_start_intraday(dt: datetime, interval_minutes: int) -> datetime:
    """m/h: floor within the bar's own calendar day -- never crosses midnight."""
    midnight = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes_since_midnight = dt.hour * 60 + dt.minute
    floored = (minutes_since_midnight // interval_minutes) * interval_minutes
    return midnight + timedelta(minutes=floored)


def _bucket_start_days(dt: datetime, interval_days: int, origin: _date) -> datetime:
    """d: floor a day-count taken relative to the stream's first bar."""
    day_offset = (dt.date() - origin).days
    floored_days = (day_offset // interval_days) * interval_days
    return datetime.combine(origin + timedelta(days=floored_days), _MIDNIGHT)


def _bucket_start_weeks(dt: datetime, interval_weeks: int) -> datetime:
    """w: floor relative to a fixed Monday -- the grid never depends on input."""
    span_days = interval_weeks * 7
    day_offset = (dt.date() - _WEEK_EPOCH).days
    floored_days = (day_offset // span_days) * span_days
    return datetime.combine(_WEEK_EPOCH + timedelta(days=floored_days), _MIDNIGHT)


def _bucket_start_months(dt: datetime, interval_months: int, origin: _date) -> datetime:
    """M: floor a month-count taken relative to the stream's first bar's month.

    Months vary in length, so this counts whole months (year * 12 + month)
    rather than days -- the only unit that can't be expressed as a fixed
    number of minutes.
    """
    origin_index = origin.year * 12 + (origin.month - 1)
    bar_index = dt.year * 12 + (dt.month - 1)
    floored_index = origin_index + (bar_index - origin_index) // interval_months * interval_months
    year, month0 = divmod(floored_index, 12)
    return datetime(year, month0 + 1, 1)


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


def resample_bars(bars: Iterable[Bar], interval: str) -> Iterator[Bar]:
    """Collapse `bars` onto buckets sized and anchored by `interval`.

    OHLC follows the usual rule -- open of the bucket's first bar, high/low
    extremes, close of its last -- tick/real volume sum, spread averages
    (None if no source bar carried one). A bucket is emitted as soon as a bar
    from the next one is seen, plus a final bucket when the stream ends, so
    this is a generator: nothing is buffered beyond the bucket in progress
    (m/h/w) or beyond that plus the stream's first bar (d/M, to fix their
    origin).

    The four units are intentionally not anchored the same way: m/h reset
    every calendar day (a bar never spans midnight) rather than pandas'
    default of drifting across days for widths that don't divide 1440 evenly;
    d and M anchor to the stream's own first bar (matching pandas'
    `origin='start_day'` default for fixed-duration offsets) rather than a
    fixed calendar point, so resampling a different subset of the same data
    can shift where multi-day/multi-month buckets fall; w anchors to Monday,
    fixed, regardless of input. All deliberate -- see the module docstring.
    """
    amount, unit = _parse_interval(interval)

    origin: _date | None = None
    current_start: datetime | None = None
    current_bars: list[Bar] = []

    for bar in bars:
        if origin is None:
            origin = bar.dt.date()

        if unit in _MINUTES_PER_UNIT:
            bucket_start = _bucket_start_intraday(bar.dt, amount * _MINUTES_PER_UNIT[unit])
        elif unit == "d":
            bucket_start = _bucket_start_days(bar.dt, amount, origin)
        elif unit == "w":
            bucket_start = _bucket_start_weeks(bar.dt, amount)
        else:
            bucket_start = _bucket_start_months(bar.dt, amount, origin)

        if current_start is not None and bucket_start != current_start:
            yield _squash(current_start, current_bars)
            current_bars = []

        current_start = bucket_start
        current_bars.append(bar)

    if current_bars:
        yield _squash(current_start, current_bars)
