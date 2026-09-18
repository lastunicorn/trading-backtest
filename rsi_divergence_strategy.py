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
M5 through the same shared loader the research pipeline uses
(`application.build_clean_dataset_use_case`), so a scan sees exactly the bars
the pipeline would. That loader hands back raw broker-server time
(America/New_York); this script shifts it to `--timezone` (default: UTC,
via `domain.pandas_approach.shift_timezone`) before scanning, so every
printed timestamp -- and the RSI/pivot calculation, which is order- not
timezone-sensitive -- lines up with UTC clocks. Nothing is written to disk.
Only divergences that cross
into the RSI 30-70 band are shown -- the older pivot's RSI value outside
`--rsi-lower`/`--rsi-upper` and the newer pivot's value inside it -- since
those are the ones that mark the oscillator actually leaving overbought/
oversold territory. Each one prints as "<kind>: <start time> -> <end time>",
the two pivot bars the divergence line connects, oldest first.

Tooling, not a research stage: versionless and freely editable.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.build_clean_dataset_use_case import build_clean_dataset
from domain.pandas_approach.divergence import Divergence, find_divergences
from domain.pandas_approach.rsi import rsi
from domain.pandas_approach.shift_timezone import shift_timezone

WIDTH = 90

GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def _colorize(divergence: Divergence, enabled: bool) -> str:
    line = f"{divergence.kind:<17} {divergence.start_time} -> {divergence.end_time}"
    if not enabled:
        return line
    color = GREEN if "Bullish" in divergence.kind else RED
    return f"{color}{line}{RESET}"


def main() -> int:
    start_time = time.perf_counter()
    args = _parse_args()

    try:
        target_tz = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError:
        print(f"ERROR: unknown timezone {args.timezone!r}", file=sys.stderr)
        return 1

    print("=" * WIDTH)
    print("EURUSD RSI DIVERGENCE SCAN")
    print("=" * WIDTH)
    print("Source:", args.source)
    print("Timezone:", args.timezone, "(source is America/New_York broker-server time)")

    dataset = build_clean_dataset(args.source, timeframe="M5", progress=print)
    df = shift_timezone(dataset.frame, target_tz)

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
        if not (args.rsi_lower <= d.start_value <= args.rsi_upper)
        and args.rsi_lower <= d.end_value <= args.rsi_upper
    ]

    print(f"\n{len(divergences)} divergence(s) found "
          f"(start outside {args.rsi_lower}-{args.rsi_upper}, end inside):")
    print("-" * WIDTH)

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


if __name__ == "__main__":
    raise SystemExit(main())
