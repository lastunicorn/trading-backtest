#!/usr/bin/env python3
"""Detect RSI divergences on M15 EURUSD bars resampled from raw M1 exports.

Python translation of `temp/RSI Divergence Indicator.pine` (the LuxAlgo-style
regular/hidden divergence indicator): find pivot points in RSI, pair each with
the previous pivot of the same kind, and flag a divergence wherever RSI and
price disagree on direction. See `domain/divergence.py` for the algorithm.

    python3 rsi_divergence.py data/eurusd/1min
    python3 rsi_divergence.py data/eurusd/1min/EURUSD_2024_03.csv
    python3 rsi_divergence.py data/eurusd/1min --hidden --rsi-length 21

`source` is a folder of raw M1 exports or a single M1 csv file -- resampled to
M15 bars (`TIMEFRAME`) with the same `ports`/`domain` building blocks the
research pipeline uses (per-file resample, then a stable-sort dedup across
files, matching the pipeline's stage-0 convention), so a scan sees the same
bars the pipeline would. The result is raw broker-server time (America/New_York); this script
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
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from application.load_historical_data_use_case import load_mt5
from domain.pandas_approach.divergence import Divergence, Direction, filter_regular_by_band, find_divergences
from domain.pandas_approach.divergence_positions import DivergencePosition, open_positions
from domain.pandas_approach.rsi import rsi
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.pandas_approach.side import Side
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

SCREEN_WIDTH = 90

# The bar size the scan runs on -- the same one `strategies.rsi_divergence` was
# built for.
TIMEFRAME = SampleSize.Parse("15m")


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

    frame = load_mt5(args.source, TIMEFRAME, EurUsd(), progress=print).data
    df = shift_timezone(frame, target_tz)

    print(f"\n{len(df):,} {TIMEFRAME} bars, {df['datetime'].min()} -> {df['datetime'].max()}")

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

    divergences = filter_regular_by_band(divergences, args.rsi_lower, args.rsi_upper)

    print(f"\n{len(divergences)} divergence(s) found "
          f"(regular divergences filtered to start outside "
          f"{args.rsi_lower}-{args.rsi_upper}, end inside):")
    print("-" * SCREEN_WIDTH)

    color = sys.stdout.isatty() and "NO_COLOR" not in os.environ

    for divergence in divergences:
        print(_colorize(divergence, color))

    positions = open_positions(
        df, divergences,
        pivot_right=args.pivot_right,
        rsi_lower=args.rsi_lower,
        rsi_upper=args.rsi_upper,
    )

    print(f"\n{len(positions)} position(s) opened "
          f"(one per regular divergence, as soon as its pivot is confirmed "
          f"-- {args.pivot_right} bar(s) after it forms):")
    print("-" * SCREEN_WIDTH)

    for position in positions:
        print(_colorize_position(position, color))

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


def _colorize_position(position: DivergencePosition, enabled: bool) -> str:
    divergence = position.divergence
    line = (
        f"{position.side.value:<6}"
        f"{position.open_time} @ {position.open_price:.5f}   "
        f"(divergence {divergence.start_time} -> {divergence.end_time})"
    )

    if not enabled:
        return line

    color = GREEN if position.side == Side.LONG else RED
    return f"{color}{line}{RESET}"


if __name__ == "__main__":
    raise SystemExit(main())
