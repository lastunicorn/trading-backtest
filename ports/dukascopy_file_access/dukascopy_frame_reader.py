"""Dukascopy M1 bid/ask CSV pairs -> a DataFrame in the repo's bar-frame shape.

Finding, pairing and reading the files is `libs.dukascopy_csv`, which hands
back each side on its own. This port decides how the two sides become one
bar: OHLC from bid, a spread column from ask - bid, and the same columns as
the MT5 reader's frames.

    from ports.dukascopy_file_access import read_path

    read_path("/data/dukascopy/eurusd")        # every pair under a folder, searched recursively
    read_path("/data/dukascopy/eurusd/2026")   # one year of them
    read_path(".../eurusd-m1-bid-2026-01-01-2026-02-01.csv")   # the pair one file belongs to
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from libs.dukascopy_csv import DukascopyFile, DukascopyFilePair, find_files, find_pair, pair_files, read_file

__all__ = ["FRAME_COLUMNS", "read_path"]

# Same shape as the MT5 reader's frames. tick_volume/volume have no
# source on either side of a Dukascopy export, so they are always empty.
FRAME_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "volume",
    "spread",
)

_OHLC = ("open", "high", "low", "close")

_EMPTY_COLUMNS = ("tick_volume", "volume")


def read_path(path: str | Path) -> pd.DataFrame:
    """Dukascopy M1 bars from every bid/ask pair under folder `path`, or from the one pair a file belongs to.

    `path` may be a folder (searched recursively, so the whole export folder
    or one year of it) or either file of a pair. Columns are `datetime`
    (naive, UTC) followed by `FRAME_COLUMNS`: OHLC from the bid file,
    `tick_volume`/`volume` always NaN, `spread` the row-average of
    (ask - bid) across OHLC, in price units.

    Pairs are concatenated in calendar order. Parsing and pairing only -- no
    sorting within a file, no dedup of duplicate timestamps. That stays a
    `domain/` decision, same as the MT5 frame reader.
    """
    path = Path(path)
    if path.is_file():
        pairs = [find_pair(path)]
    else:
        pairs = pair_files(find_files(path))
        if not pairs:
            raise FileNotFoundError(f"no Dukascopy bid/ask files under {path}")

    parts = [_read_pair(pair) for pair in pairs]
    frame = parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)

    return frame[["datetime", *FRAME_COLUMNS]]


def _read_side(file: DukascopyFile) -> pd.DataFrame:
    """One price side: naive-UTC datetime + OHLC (any other column the file has is dropped)."""
    frame = read_file(file)
    frame["datetime"] = frame["datetime"].dt.tz_localize(None)
    return frame[["datetime", *_OHLC]]


def _read_pair(pair: DukascopyFilePair) -> pd.DataFrame:
    """One period: OHLC from the bid side, spread averaged from ask - bid.

    A left join on the bid side, not an inner join: a handful of known dates
    have rows on one side missing from the other (see the data folder's
    ANOMALIES.md). OHLC always comes from bid, so a bid row is kept even when
    its ask counterpart is missing -- spread is just NaN there rather than the
    whole bar being dropped.
    """
    bid = _read_side(pair.bid)
    ask = _read_side(pair.ask)

    merged = bid.merge(ask, on="datetime", how="left", suffixes=("", "_ask"))
    spread = pd.concat(
        [merged[f"{column}_ask"] - merged[column] for column in _OHLC], axis=1
    ).mean(axis=1)

    frame = merged[["datetime", *_OHLC]].copy()
    for column in _EMPTY_COLUMNS:
        frame[column] = float("nan")
    frame["spread"] = spread

    return frame
