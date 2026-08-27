"""Bars -> DataFrame, and one timeframe -> a coarser one.

The first step out of the port: `ports.mt5_file_access` hands back `Bar`
objects, and this module turns them into the table shape the research pipeline
works in -- ``datetime, open, high, low, close, tick_volume, volume, spread``,
with the trailing columns present only when the export actually carried them --
then collapses that table onto a coarser grid.

    from domain.frames import read_frame, resample_ohlc

    m1 = read_frame("data/eurusd/1min/EURUSD_2020_01.csv")
    m5 = resample_ohlc(m1, "5min")

Deduplication lives here too: a timestamp that appears twice in one export keeps
its later row, which is a decision about the data, not about the file format.
No parsing rule is re-implemented here -- that all stays in the port.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from ports.mt5_file_access import Bar, detect_layout, iter_bars

__all__ = ["FRAME_COLUMNS", "read_frame", "resample_ohlc", "write_frame"]

# Column order the pipeline's clean CSVs use. `real_volume` is spelled `volume`
# in the frame, the name the research scripts already read.
FRAME_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "volume", "spread"
)

# Frame column -> the name the Bar attribute and `detect_layout` both use.
_BAR_ATTRS = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "tick_volume": "tick_volume",
    "volume": "real_volume",
    "spread": "spread",
}

OHLC = [
    "open",
    "high",
    "low",
    "close"
]

# How each column collapses when bars are merged into a longer timeframe.
_AGGREGATIONS = {
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "tick_volume": "sum",
    "volume": "sum",
    "spread": "mean",
}


def _bars_to_frame(
    bars: Iterable[Bar],
    *,
    columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Build a DataFrame from Bars, in file order.

    columns -- which of FRAME_COLUMNS to keep; defaults to all of them. Pass the
    subset the source file actually carried so a 7-column export does not grow a
    phantom all-zero `volume` column.
    """
    keep = [name for name in FRAME_COLUMNS if columns is None or name in set(columns)]
    rows = [
        (bar.dt, *(getattr(bar, _BAR_ATTRS[name]) for name in keep))
        for bar in bars
    ]

    return pd.DataFrame(rows, columns=["datetime", *keep])


def read_frame(
    path,
    *,
    strict: bool = False,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> pd.DataFrame:
    """Read one MT5 export into a sorted, timestamp-deduplicated DataFrame.

    Defaults to strict=False -- a malformed line is dropped rather than fatal,
    which is how the loader has always treated unparsable rows. Pass `on_skip`
    to count or log them.
    """
    path = str(path)
    layout = detect_layout(path)
    present = {name for name, field in _BAR_ATTRS.items() if field in layout}

    frame = _bars_to_frame(
        iter_bars(path, strict=strict, on_skip=on_skip),
        columns=present,
    )

    if frame.empty:
        return frame

    frame = frame.sort_values("datetime", kind="stable")

    return frame.drop_duplicates("datetime", keep="last").reset_index(drop=True)


def resample_ohlc(frame: pd.DataFrame, rule: str = "5min") -> pd.DataFrame:
    """Collapse bars onto a coarser grid: OHLC by first/max/min/last.

    Volumes sum, spread averages. Bins with no source bar are dropped rather
    than emitted as gaps.
    """
    if frame.empty:
        return pd.DataFrame()

    indexed = frame.set_index("datetime")
    agg = {
        name: how
        for name, how in _AGGREGATIONS.items()
        if name in indexed.columns
    }

    resampled = indexed.resample(rule).agg(agg)

    return resampled.dropna(subset=OHLC).reset_index()


def write_frame(frame: pd.DataFrame, path: str) -> None:
    """Write a DataFrame to a CSV file."""
    frame.to_csv(path, index=False)