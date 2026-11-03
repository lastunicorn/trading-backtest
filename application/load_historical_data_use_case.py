"""Load bars from any of the repo's sources into a `HistoricalData`.

    from application.load_historical_data_use_case import (
        SourceFormat, load_dukascopy, load_histdata, load_mt5, load_source)

    M5 = SampleSize.Parse("5m")
    data = load_mt5("data/eurusd/1min", M5, EURUSD, timezone=BROKER_SERVER_TZ, progress=print)
    data = load_dukascopy("/data/dukascopy/eurusd/2025", M5, EURUSD, timezone=ZoneInfo("UTC"))
    data = load_histdata(".../histdata/mt/2025", M5, EURUSD, timezone=ZoneInfo("America/New_York"))
    data = load_source(path, SourceFormat.METATRADER, M5, symbol, timezone=tz)   # the loader for a format

Each format differs in layout and spread unit, and this module is where those
differences are settled:

    format                                   spread unit
    MT4/MT5 exports                           points
    histdata.com MetaTrader downloads         -- (no spread, no volume)
    Dukascopy bid/ask pairs                   price

The clock is *not* a property of the format -- MT exports from this repo's
broker are on the broker-server clock (New York + 7h), histdata's MT exports
on New York time -- so every loader takes the source's `timezone` from the
caller. It labels the bars; nothing is shifted. A format whose clock is fixed
(Dukascopy's UTC, histdata's New York time) checks it rather than trusting it.

Every loader resamples to `timeframe`. That is a no-op when the source is
already at it, as an M5 export (`read_csv.py --interval 5m --output`)
is for "5m". It is wrong for a timeframe *finer* than the source, which no
loader can detect -- asking for M1 from an M5 file gives the M5 bars back
labelled M1.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from enum import Enum
from zoneinfo import ZoneInfo

import pandas as pd

from application.build_clean_dataset_use_case import build_clean_dataset
from domain.pandas_approach.frames import clean_frame, resample_ohlc
from domain.pandas_approach.historical_data import HistoricalData, SpreadUnit
from domain.sample_size import SampleSize
from domain.symbol import Symbol
from ports import dukascopy, histdata_file_access

__all__ = ["SourceFormat", "load_dukascopy", "load_histdata", "load_mt5", "load_source"]

Progress = Callable[[str], None]


class SourceFormat(Enum):
    """How a source's files are laid out, which decides the loader. Values are the config's `data_source.format`."""

    METATRADER = "metatrader"   # MT4/MT5 exports: a folder of them, or one
    HISTDATA = "histdata"       # histdata.com MetaTrader downloads: a folder of them, or one
    DUKASCOPY = "dukascopy"     # bid/ask pairs: a folder of them, or one file of a pair


def load_source(
    source,
    source_format: SourceFormat,
    timeframe: SampleSize,
    symbol: Symbol,
    *,
    timezone: tzinfo,
    progress: Progress | None = None,
) -> HistoricalData:
    """`source` read by the loader for `source_format`, its bars on the `timezone` clock."""
    if source_format is SourceFormat.METATRADER:
        return load_mt5(source, timeframe, symbol, timezone=timezone, progress=progress)
    if source_format is SourceFormat.HISTDATA:
        return load_histdata(source, timeframe, symbol, timezone=timezone, progress=progress)
    if source_format is SourceFormat.DUKASCOPY:
        return load_dukascopy(source, timeframe, symbol, timezone=timezone, progress=progress)
    raise ValueError(f"unknown source format {source_format!r}")


def load_mt5(
    source, timeframe: SampleSize, symbol: Symbol, *, timezone: tzinfo, progress: Progress | None = None,
) -> HistoricalData:
    """A folder of MT5 exports, or one export, merged and resampled.

    Built by `build_clean_dataset`: each file resampled on its own,
    then deduplicated across files with the later file winning. A file that
    fails to parse is reported through `progress` and skipped.
    """
    frame = build_clean_dataset(source, timeframe=timeframe, progress=progress)
    return HistoricalData.from_frame(frame, timeframe, symbol, spread_unit=SpreadUnit.POINTS, timezone=timezone)


def load_histdata(
    source, timeframe: SampleSize, symbol: Symbol, *, timezone: tzinfo, progress: Progress | None = None,
) -> HistoricalData:
    """A folder of histdata.com MetaTrader downloads (`DAT_MT_*.csv`), or one, merged and resampled.

    Built by `build_clean_dataset`, like `load_mt5`. histdata's timestamps are
    New York time: `timezone` must keep New York's clock, and any other raises
    `ValueError` rather than mislabelling the bars.

    The bars carry no volume and no spread (histdata has neither).
    """
    if not _same_clock(timezone, ZoneInfo(histdata_file_access.TIMEZONE)):
        raise ValueError(f"histdata bars are {histdata_file_access.TIMEZONE} time, not {timezone}")
    frame = build_clean_dataset(
        source,
        timeframe=timeframe,
        pattern=histdata_file_access.FILE_PATTERN,
        read_file=histdata_file_access.read_frame,
        progress=progress,
    )
    return HistoricalData.from_frame(frame, timeframe, symbol, timezone=timezone)


def load_dukascopy(
    source, timeframe: SampleSize, symbol: Symbol, *, timezone: tzinfo, progress: Progress | None = None,
) -> HistoricalData:
    """Dukascopy M1 bid/ask pairs under folder `source` (or the pair one file belongs to), resampled.

    Dukascopy timestamps are epoch milliseconds, so UTC by definition:
    `timezone` must be a UTC zone, and any other raises `ValueError` rather
    than mislabelling the bars.

    Dukascopy has no volume, so the empty volume columns are dropped rather
    than resampled into zeros.
    """
    if not _is_utc(timezone):
        raise ValueError(f"Dukascopy bars are UTC (epoch timestamps), not {timezone}")
    if progress is not None:
        progress(f"Reading Dukascopy {source}...")
    raw = dukascopy.read_path(source).drop(columns=["tick_volume", "volume"])
    frame = resample_ohlc(clean_frame(raw), timeframe)
    return HistoricalData.from_frame(frame, timeframe, symbol, spread_unit=SpreadUnit.PRICE, timezone=timezone)


def _is_utc(zone: tzinfo) -> bool:
    """Whether `zone` is UTC all year (checked in winter and summer, so a DST zone fails)."""
    return all(datetime(2020, month, 1, tzinfo=zone).utcoffset() == timedelta(0) for month in (1, 7))


def _same_clock(zone: tzinfo, expected: tzinfo) -> bool:
    """Whether `zone` keeps `expected`'s wall clock, in winter, in summer and in the weeks US and EU DST disagree."""
    moments = [datetime(2020, month, day) for month, day in ((1, 1), (3, 15), (7, 1), (10, 30))]
    return all(moment.replace(tzinfo=zone).utcoffset() == moment.replace(tzinfo=expected).utcoffset() for moment in moments)
