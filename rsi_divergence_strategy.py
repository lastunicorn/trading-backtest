#!/usr/bin/env python3
"""Detect RSI divergences on M5 EURUSD bars resampled from raw M1 exports.

Python translation of `temp/RSI Divergence Indicator.pine` (the LuxAlgo-style
regular/hidden divergence indicator): find pivot points in RSI, pair each with
the previous pivot of the same kind, and flag a divergence wherever RSI and
price disagree on direction. See `domain/divergence.py` for the algorithm.

    python3 rsi_divergence.py data/eurusd/1min
    python3 rsi_divergence.py data/eurusd/1min/EURUSD_2024_03.csv
    python3 rsi_divergence.py data/eurusd/1min --hidden --rsi-length 21

`source` is a folder of raw M1 exports or a single M1 csv file -- resampled to
M5 bars with the same `ports`/`domain` building blocks the research pipeline
uses (per-file resample, then a stable-sort dedup across files, matching the
pipeline's stage-0 convention), so a scan sees the same bars the pipeline
would. The result is raw broker-server time (America/New_York); this script
shifts it to `--timezone` (default: UTC, via
`domain.pandas_approach.shift_timezone`) before scanning, so every printed
timestamp -- and the RSI/pivot calculation, which is order- not
timezone-sensitive -- lines up with UTC clocks. Nothing is written to disk.
For regular divergences only, the 30-70 band filter applies: the older
pivot's RSI value must be outside `--rsi-lower`/`--rsi-upper` and the newer
pivot's value inside it, since those are the ones that mark the oscillator
actually leaving overbought/oversold territory. Hidden divergences (shown
only with `--hidden`) are not band-filtered, since they occur mid-trend
rather than at the extremes the 30-70 band is meant to isolate. Each one
prints as "<kind>: <start time> -> <end time>", the two pivot bars the
divergence line connects, oldest first.

Tooling, not a research stage: versionless and freely editable.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from domain.pandas_approach.divergence import Category, Divergence, Direction, find_divergences
from domain.pandas_approach.frames import clean_frame, resample_ohlc
from domain.pandas_approach.rsi import rsi
from domain.pandas_approach.shift_timezone import shift_timezone
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame

SCREEN_WIDTH = 90


def main() -> int:
    start_time = time.perf_counter()
    args = _parse_args()

    try:
        target_tz = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        print(f"ERROR: unknown timezone {args.timezone!r}", file=sys.stderr)
        return 1

    print("=" * SCREEN_WIDTH)
    print("EURUSD RSI DIVERGENCE SCAN")
    print("=" * SCREEN_WIDTH)
    print("Source:", args.source)
    print("Timezone:", args.timezone, "(source is America/New_York broker-server time)")

    frame = _load_m5_frame(args.source, progress=print)
    df = shift_timezone(frame, target_tz)

    print(f"\n{len(df):,} M5 bars, {df['datetime'].min()} -> {df['datetime'].max()}")

    oscillator = rsi(df["close"], length=args.rsi_length)

    divergences = find_divergences(
        df,
        oscillator,
        pivot_left=args.pivot_left,
        pivot_right=args.pivot_right,
        range_lower=args.range_lower,
        range_upper=args.range_upper,
        include_hidden=args.hidden,
    )

    divergences = [
        d for d in divergences
        if d.category != Category.REGULAR
        or (
            not (args.rsi_lower <= d.start_value <= args.rsi_upper)
            and args.rsi_lower <= d.end_value <= args.rsi_upper
        )
    ]

    print(f"\n{len(divergences)} divergence(s) found "
          f"(regular divergences filtered to start outside "
          f"{args.rsi_lower}-{args.rsi_upper}, end inside):")
    print("-" * SCREEN_WIDTH)

    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ

    for divergence in divergences:
        print(_colorize(divergence, color))

    elapsed = time.perf_counter() - start_time
    print()
    print(f"Execution time: {elapsed:.2f}s")

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    parser.add_argument("source",
        help="folder of raw MT5 M1 exports, or a single M1 csv file")

    parser.add_argument("--rsi-length", type=int, default=14,
        help="RSI period (default: 14)")

    parser.add_argument("--pivot-left", type=int, default=5,
        help="bars to the left a pivot must beat (default: 5)")

    parser.add_argument("--pivot-right", type=int, default=5,
        help="bars to the right a pivot must beat -- also the confirmation "
             "delay in the original indicator (default: 5)")

    parser.add_argument("--range-lower", type=int, default=5,
        help="minimum bars between two pivots for a divergence (default: 5)")

    parser.add_argument("--range-upper", type=int, default=60,
        help="maximum bars between two pivots for a divergence (default: 60)")

    parser.add_argument("--hidden", action="store_true",
        help="also report hidden divergences (off by default, matching the "
             "Pine indicator's defaults)")

    parser.add_argument("--rsi-lower", type=float, default=30,
        help="lower bound of the RSI 'inside' band (default: 30)")

    parser.add_argument("--rsi-upper", type=float, default=70,
        help="upper bound of the RSI 'inside' band (default: 70)")

    parser.add_argument("--timezone", default="UTC",
        help="IANA timezone to shift the broker-server (America/New_York) "
             "source data into before scanning and display (default: UTC)")

    return parser.parse_args()


def _load_m5_frame(source: str, progress: Callable[[str], None]) -> pd.DataFrame:
    """Resample every M1 export under `source` to M5 bars and merge them.

    Each file is resampled on its own before concatenation, so peak memory is
    one month rather than the whole history. Where two files cover the same
    timestamp the later-sorted one wins (stable sort + keep-last dedup),
    matching the pipeline's stage-0 convention.
    """
    file_paths = find_files(source)
    progress(f"Found {len(file_paths)} candidate source CSV files.")

    pieces: list[pd.DataFrame] = []
    for index, path in enumerate(file_paths, 1):
        progress(f"[{index}/{len(file_paths)}] {path.name}")
        raw = read_frame(path, strict=False)
        bars = resample_ohlc(clean_frame(raw), "M15") if not raw.empty else pd.DataFrame()
        if bars.empty:
            progress("    SKIP: no usable rows")
            continue
        progress(f"    OK: {len(raw):,} source rows -> {len(bars):,} bars")
        pieces.append(bars)

    if not pieces:
        raise RuntimeError("No usable source files.")

    progress("Combining converted pieces...")
    big_frame = pd.concat(pieces, ignore_index=True)
    return clean_frame(big_frame)

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def _colorize(divergence: Divergence, enabled: bool) -> str:
    category = divergence.category.value
    direction = divergence.direction.value
    if(divergence.start_time.date() == divergence.end_time.date()):
        line = (
            f"{category:<8} {direction:<8}"
            f"{divergence.start_time} ({divergence.start_value:.2f}) -> "
            f"{divergence.end_time.time()} ({divergence.end_value:.2f})"
        )
    else:
        line = (
            f"{category:<8} {direction:<8}"
            f"{divergence.start_time} ({divergence.start_value:.2f}) -> "
            f"{divergence.end_time} ({divergence.end_value:.2f})"
        )

    if not enabled:
        return line

    color = GREEN if divergence.direction == Direction.BULLISH else RED
    return f"{color}{line}{RESET}"


if __name__ == "__main__":
    raise SystemExit(main())
