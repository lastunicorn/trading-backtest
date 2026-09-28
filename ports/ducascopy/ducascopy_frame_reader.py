"""Dukascopy M1 bid/ask CSV pairs -> a DataFrame in the pipeline's frame shape.

Dukascopy ships one month of data per file, split into a bid file and an ask
file with matching names apart from the `bid`/`ask` marker
(`eurusd-m1-bid-2020-01-01-2020-02-01.csv` / `eurusd-m1-ask-...`). Each file is
just `timestamp,open,high,low,close` -- epoch milliseconds (UTC) and one price
side. There is no volume field on either side, and no combined spread column:
this reader builds one from the two files, which is the only reason it reads
a pair at all rather than one file at a time.

    from ports.ducascopy import read_frame

    read_frame(2020)          # every bid/ask pair for 2020, concatenated
    read_frame(2020, 3)       # March 2020 only

The export folder is read from `config.DATA_DIR` (see `config.example.py` --
`config.py` itself is gitignored, machine-specific) unless `data_dir` is
passed explicitly.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

try:
    from ports.ducascopy import config
except ImportError:
    config = None

__all__ = ["FRAME_COLUMNS", "read_frame"]

# Same shape the rest of the pipeline's frames use. tick_volume/volume have no
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


def _default_data_dir() -> Path:
    if config is None or not hasattr(config, "DATA_DIR"):
        raise RuntimeError(
            "No Dukascopy data directory configured -- copy "
            "ports/ducascopy/config.example.py to ports/ducascopy/config.py "
            "and set DATA_DIR, or pass data_dir= explicitly."
        )
    return Path(config.DATA_DIR)


def _find_pairs(data_dir: Path, year: int, month: int | None) -> list[tuple[Path, Path]]:
    """Locate the bid/ask file(s) for `year` (and `month`, if given).

    Matches on the filename's own start date rather than trusting the year
    subfolder a file happens to sit in: at least one export (December 2025)
    is filed under the following year's folder, so an unqualified glob under
    `data_dir / year` would silently miss it. `rglob` searches every
    subfolder instead, and the pattern anchors on the filename's start date
    (`bid-2020-03-01-...`), which is always the true calendar month.
    """
    month_glob = f"{month:02d}" if month is not None else "*"
    pattern = f"eurusd-m1-{{side}}-{year:04d}-{month_glob}-01-*.csv"

    bid_files = sorted(data_dir.rglob(pattern.format(side="bid")), key=lambda p: p.name)
    ask_files = sorted(data_dir.rglob(pattern.format(side="ask")), key=lambda p: p.name)

    if month is not None:
        if not bid_files or not ask_files:
            raise FileNotFoundError(
                f"No Dukascopy bid/ask file pair for {year:04d}-{month:02d} under {data_dir}"
            )
        return [(bid_files[0], ask_files[0])]

    if not bid_files or not ask_files:
        raise FileNotFoundError(f"No Dukascopy bid/ask files for {year:04d} under {data_dir}")

    bid_names = [p.name.replace("bid", "") for p in bid_files]
    ask_names = [p.name.replace("ask", "") for p in ask_files]
    if bid_names != ask_names:
        raise FileNotFoundError(
            f"Mismatched Dukascopy bid/ask file sets for {year:04d} under {data_dir}: "
            f"bid has {[p.name for p in bid_files]}, ask has {[p.name for p in ask_files]}"
        )

    return list(zip(bid_files, ask_files))


def _read_side(path: Path) -> pd.DataFrame:
    """One Dukascopy price-side file: timestamp (epoch ms, UTC) + OHLC."""
    frame = pd.read_csv(path, usecols=["timestamp", *_OHLC])
    frame["datetime"] = pd.to_datetime(frame["timestamp"], unit="ms")
    return frame.drop(columns="timestamp")


def _read_pair(bid_path: Path, ask_path: Path) -> pd.DataFrame:
    """One month: OHLC from the bid side, spread averaged from ask - bid.

    A left join on the bid side, not an inner join: a handful of known dates
    have rows on one side missing from the other (see the data folder's
    ANOMALIES.md). OHLC always comes from bid, so a bid row is kept even when
    its ask counterpart is missing -- spread is just NaN there rather than the
    whole bar being dropped.
    """
    bid = _read_side(bid_path)
    ask = _read_side(ask_path)

    merged = bid.merge(ask, on="datetime", how="left", suffixes=("", "_ask"))
    spread = pd.concat(
        [merged[f"{column}_ask"] - merged[column] for column in _OHLC], axis=1
    ).mean(axis=1)

    frame = merged[["datetime", *_OHLC]].copy()
    for column in _EMPTY_COLUMNS:
        frame[column] = float("nan")
    frame["spread"] = spread

    return frame


def read_frame(year: int, month: int | None = None, *, data_dir: str | Path | None = None) -> pd.DataFrame:
    """Dukascopy EURUSD M1 bars for one year, or one month of it.

    `month` is 1-12; omitted, every month present for `year` is concatenated
    in calendar order. Columns are `datetime` followed by `FRAME_COLUMNS`:
    OHLC from the bid file, `tick_volume`/`volume` always NaN (Dukascopy has
    no volume field), `spread` the row-average of (ask - bid) across OHLC.

    Parsing and pairing only -- no sorting beyond calendar file order, no
    dedup of duplicate timestamps within a file. That stays a `domain/`
    decision, same as the MT5 frame reader.
    """
    base = Path(data_dir) if data_dir is not None else _default_data_dir()
    pairs = _find_pairs(base, year, month)

    parts = [_read_pair(bid_path, ask_path) for bid_path, ask_path in pairs]
    frame = parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)

    return frame[["datetime", *FRAME_COLUMNS]]
