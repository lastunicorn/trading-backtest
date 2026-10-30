"""Dukascopy M1 bid/ask CSV pairs -> a DataFrame in the repo's bar-frame shape.

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
    read_path("/data/ducascopy/eurusd/2026")   # every pair under a folder, or one pair

`read_frame` looks in `config.DATA_DIR` (see `config.example.py` --
`config.py` itself is gitignored, machine-specific) unless `data_dir` is
passed explicitly. `read_path` takes the location itself and needs no config.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

try:
    from ports.ducascopy import config
except ImportError:
    config = None

__all__ = ["FRAME_COLUMNS", "read_frame", "read_path"]

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


# A Dukascopy export's name: `<instrument>-<timeframe>-<side>-<start date>-<end>.csv`.
# The end is a date for a whole month but a download time for a partial one,
# and it differs between the two sides then (`...-2026-09-21T16-57` bid,
# `...-2026-09-21T17-14` ask), so a pair is matched on everything before it.
_EXPORT_NAME = re.compile(r"(?P<prefix>.+)-(?P<side>bid|ask)-(?P<start>\d{4}-\d{2}-\d{2})-.*\.csv")


def _pairs_under(path: Path) -> list[tuple[Path, Path]]:
    """Every bid/ask pair in folder `path` (searched recursively), or the pair `path` is one side of.

    A pair is a bid and an ask file in the same folder with the same
    instrument and start date. Sorted by file name, which is calendar order:
    the name starts with the month it covers, whichever year folder it sits in.
    """
    if path.is_file():
        match = _EXPORT_NAME.fullmatch(path.name)
        if match is None:
            raise ValueError(f"{path} is not a Dukascopy export: expected a name like eurusd-m1-bid-2020-01-01-2020-02-01.csv")
        candidates = [candidate for candidate in path.parent.glob(f"{match['prefix']}-*-{match['start']}-*.csv")]
    elif path.is_dir():
        candidates = list(path.rglob("*.csv"))
    else:
        raise FileNotFoundError(f"no Dukascopy export at {path}")

    sides: dict[tuple[Path, str, str], dict[str, Path]] = {}
    for candidate in candidates:
        match = _EXPORT_NAME.fullmatch(candidate.name)
        if match is None:
            continue
        pair = sides.setdefault((candidate.parent, match["prefix"], match["start"]), {})
        if match["side"] in pair:
            raise ValueError(f"two Dukascopy {match['side']} files for one month: {pair[match['side']]} and {candidate}")
        pair[match["side"]] = candidate

    incomplete = [next(iter(pair.values())) for pair in sides.values() if len(pair) != 2]
    if incomplete:
        raise FileNotFoundError(f"Dukascopy file(s) without the other side of their pair: {', '.join(map(str, incomplete))}")
    if not sides:
        raise FileNotFoundError(f"no Dukascopy bid/ask files under {path}")
    return sorted(((pair["bid"], pair["ask"]) for pair in sides.values()), key=lambda bid_ask: bid_ask[0].name)


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


def read_path(path: str | Path) -> pd.DataFrame:
    """Dukascopy M1 bars from every bid/ask pair under folder `path`, or from the one pair a file belongs to.

    `path` may be a folder (searched recursively, so the whole export folder
    or one year of it) or either file of a pair. Same columns and the same
    no-cleaning rule as `read_frame`; pairs are concatenated in calendar order.
    """
    parts = [_read_pair(bid_path, ask_path) for bid_path, ask_path in _pairs_under(Path(path))]
    frame = parts[0] if len(parts) == 1 else pd.concat(parts, ignore_index=True)

    return frame[["datetime", *FRAME_COLUMNS]]
