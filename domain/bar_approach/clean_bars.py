"""Stable-sort `Bar` objects by `dt` and drop duplicate timestamps.

The `domain.bar_approach` counterpart to `domain.pandas_approach.frames.
clean_frame`. Sorting needs the whole stream in memory -- unlike
`shift_bars`/`resample_bars`, which only need one order-preserving pass --
so this takes any iterable but returns a materialized list.

    from domain.bar_approach.clean_bars import clean_bars

    bars = clean_bars(read_bars(path))

Same rule `clean_frame` and `application.build_clean_dataset_use_case` use:
when two bars claim the same `dt`, whichever arrived later in `bars` wins.
"""

from __future__ import annotations

from collections.abc import Iterable

from domain.bar_approach.bar import Bar

__all__ = ["clean_bars"]


def clean_bars(bars: Iterable[Bar]) -> list[Bar]:
    """Stable-sort `bars` by `dt`, keeping the last bar for a repeated `dt`."""
    ordered = sorted(bars, key=lambda bar: bar.dt)

    deduped: dict = {}
    for bar in ordered:
        deduped[bar.dt] = bar

    return list(deduped.values())
