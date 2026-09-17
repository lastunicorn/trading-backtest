"""A raw frame -> a clean one, or one timeframe -> a coarser one.

Reading an export into a frame now lives in
`ports.mt5_file_access.mt5_frame_reader`; this module handles what comes after:
resolving duplicate timestamps (`clean_frame`) and collapsing bars onto a
coarser grid -- OHLC by first/max/min/last, volumes summed, spread averaged
(`resample_ohlc`).

    from domain.pandas_approach.frames import clean_frame, resample_ohlc

    m1 = clean_frame(m1)
    m5 = resample_ohlc(m1, "M5")

Timeframes are named the broker's way ("M5", "H1"). This module is the one
place that has to know the pandas resample rule they map to, so the lookup
lives here rather than being threaded through every caller.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["clean_frame", "resample_ohlc"]

# Broker timeframe label -> the pandas resample rule it means. A label the
# table does not cover is passed straight to pandas, so a raw rule still works.
_PANDAS_RULES = {
    "M1": "1min",
    "M5": "5min",
    "M15": "15min",
    "M30": "30min",
    "H1": "1h",
}

_OHLC = [
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


def clean_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Stable-sort by datetime and drop duplicate timestamps, keeping the last.

    Same rule `application.build_clean_dataset_use_case` uses when two rows
    claim the same timestamp: the sort is stable, so among rows sharing a
    timestamp, whichever arrived later in `frame` wins.
    """
    return (
        frame.sort_values("datetime", kind="stable")
        .drop_duplicates("datetime", keep="last")
        .reset_index(drop=True)
    )


def resample_ohlc(frame: pd.DataFrame, timeframe: str = "M5") -> pd.DataFrame:
    """Collapse bars onto a coarser grid: OHLC by first/max/min/last.

    `timeframe` is a broker label ("M5", "H1"); it is mapped to the pandas
    resample rule here. Volumes sum, spread averages. Bins with no source bar
    are dropped rather than emitted as gaps.
    """
    if frame.empty:
        return pd.DataFrame()

    indexed = frame.set_index("datetime")
    agg = {
        name: how
        for name, how in _AGGREGATIONS.items()
        if name in indexed.columns
    }

    rule = _PANDAS_RULES.get(timeframe, timeframe)
    resampled = indexed.resample(rule).agg(agg)

    return resampled.dropna(subset=_OHLC).reset_index()
