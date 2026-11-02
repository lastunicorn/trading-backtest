"""Reading one Dukascopy export into a DataFrame.

A candle export is `timestamp,open,high,low,close`, plus `volume` when it was
downloaded with volumes; `timestamp` is epoch milliseconds, UTC.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .dukascopy_file import DukascopyFile

__all__ = ["REQUIRED_COLUMNS", "DukascopyFormatError", "read_file"]

REQUIRED_COLUMNS = ("timestamp", "open", "high", "low", "close")


class DukascopyFormatError(ValueError):
    """A file whose contents aren't a Dukascopy candle export."""


def read_file(file: DukascopyFile | str | Path) -> pd.DataFrame:
    """Every row and column of one export, as stored.

    The only change is `timestamp` becoming a `datetime` column (timezone-aware
    UTC, first). Every other column is kept as-is, in file order. Rows stay
    in file order: no sorting, no dedup, no filling, so the source's
    anomalies (missing days, flat filler candles) reach the caller unchanged.

    Raises DukascopyFormatError if a required column is missing or a
    timestamp isn't epoch milliseconds.
    """
    path = file.path if isinstance(file, DukascopyFile) else Path(file)
    frame = pd.read_csv(path)

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise DukascopyFormatError(f"{path} is missing column(s) {', '.join(missing)}; "
                                   f"a Dukascopy export has {', '.join(REQUIRED_COLUMNS)}")
    # A header-only file has an untyped (object) column; anything else must be whole numbers.
    timestamps = frame["timestamp"]
    if not (timestamps.empty or pd.api.types.is_integer_dtype(timestamps)):
        raise DukascopyFormatError(f"{path}: timestamps aren't epoch milliseconds "
                                   f"(first value: {timestamps.iat[0]!r})")
    stamps = pd.to_datetime(timestamps.astype("int64"), unit="ms", utc=True)

    frame = frame.drop(columns="timestamp")
    frame.insert(0, "datetime", stamps)
    return frame
