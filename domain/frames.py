"""One timeframe -> a coarser one.

Reading an export into a frame now lives in
`ports.mt5_file_access.mt5_frame_reader`; this module only collapses what it's
handed onto a coarser grid -- OHLC by first/max/min/last, volumes summed,
spread averaged.

    from domain.frames import resample_ohlc

    m5 = resample_ohlc(m1, "5min")
"""

from __future__ import annotations

import pandas as pd

__all__ = ["resample_ohlc"]

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
