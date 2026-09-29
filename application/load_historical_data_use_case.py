"""Load bars from any of the repo's sources into a `HistoricalData`.

    from application.load_historical_data_use_case import (
        SourceFormat, load_clean_csv, load_dukascopy, load_mt5, load_source)

    M5 = SampleSize.Parse("5m")
    data = load_mt5("data/eurusd/1min", M5, EurUsd(), timezone=BROKER_SERVER_TZ, progress=print)
    data = load_clean_csv("output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv", M5, EurUsd(),
                          timezone=BROKER_SERVER_TZ)
    data = load_dukascopy("/data/ducascopy/eurusd/2025", M5, EurUsd(), timezone=ZoneInfo("UTC"))
    data = load_source(path, SourceFormat.METATRADER, M5, symbol, timezone=tz)   # the loader for a format

Each format differs in layout and spread unit, and this module is where those
differences are settled:

    format                                   spread unit
    MT4/MT5 exports (and resample_csv output) points
    pipeline clean CSV (v24 output)           points
    Dukascopy bid/ask pairs                   price

The clock is *not* a property of the format -- MT exports from this repo's
broker are on the broker-server clock (New York + 7h), histdata's MT exports
on New York time -- so every loader takes the source's `timezone` from the
caller. It labels the bars; nothing is shifted.

Every loader resamples to `timeframe`. That is a no-op when the source is
already at it, as the clean M5 CSV is for "5m". It is wrong for a timeframe
*finer* than the source, which no loader can detect -- asking for M1 from an
M5 file gives the M5 bars back labelled M1.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, tzinfo
from enum import Enum

import pandas as pd

from application.build_clean_dataset_use_case import build_clean_dataset
from domain.pandas_approach.frames import clean_frame, resample_ohlc
from domain.pandas_approach.historical_data import HistoricalData, SpreadUnit
from domain.sample_size import SampleSize
from domain.symbol import Symbol
from ports import ducascopy

__all__ = ["SourceFormat", "load_clean_csv", "load_dukascopy", "load_mt5", "load_source"]

Progress = Callable[[str], None]


class SourceFormat(Enum):
    """How a source's files are laid out, which decides the loader. Values are the config's `data.format`."""

    METATRADER = "metatrader"   # MT4/MT5 exports: a folder of them, or one
    DUKASCOPY = "dukascopy"     # bid/ask pairs: a folder of them, or one file of a pair
    CLEAN_CSV = "clean-csv"     # the research pipeline's clean CSV (v24 output)


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
    if source_format is SourceFormat.DUKASCOPY:
        return load_dukascopy(source, timeframe, symbol, timezone=timezone, progress=progress)
    if source_format is SourceFormat.CLEAN_CSV:
        return load_clean_csv(source, timeframe, symbol, timezone=timezone)
    raise ValueError(f"unknown source format {source_format!r}")


def load_mt5(
    source, timeframe: SampleSize, symbol: Symbol, *, timezone: tzinfo, progress: Progress | None = None,
) -> HistoricalData:
    """A folder of MT5 exports, or one export, merged and resampled.

    The stage-0 build (`build_clean_dataset`): each file resampled on its own,
    then deduplicated across files with the later file winning. A file that
    fails to parse is reported through `progress` and skipped.
    """
    dataset = build_clean_dataset(source, timeframe=timeframe, progress=progress)
    return HistoricalData.from_frame(dataset.frame, timeframe, symbol, spread_unit=SpreadUnit.POINTS, timezone=timezone)


def load_clean_csv(path, timeframe: SampleSize, symbol: Symbol, *, timezone: tzinfo) -> HistoricalData:
    """The research pipeline's clean CSV (`datetime,open,high,low,close,...`)."""
    frame = pd.read_csv(path, parse_dates=["datetime"])
    frame = resample_ohlc(clean_frame(frame), timeframe)
    return HistoricalData.from_frame(frame, timeframe, symbol, spread_unit=SpreadUnit.POINTS, timezone=timezone)


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
    raw = ducascopy.read_path(source).drop(columns=["tick_volume", "volume"])
    frame = resample_ohlc(clean_frame(raw), timeframe)
    return HistoricalData.from_frame(frame, timeframe, symbol, spread_unit=SpreadUnit.PRICE, timezone=timezone)


def _is_utc(zone: tzinfo) -> bool:
    """Whether `zone` is UTC all year (checked in winter and summer, so a DST zone fails)."""
    return all(datetime(2020, month, 1, tzinfo=zone).utcoffset() == timedelta(0) for month in (1, 7))
