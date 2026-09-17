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
the pipeline would. Nothing is written to disk; each divergence prints as
"<kind>: <start time> -> <end time>", the two pivot bars the divergence line
connects, oldest first.

Tooling, not a research stage: versionless and freely editable.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
import time

from application.build_clean_dataset_use_case import build_clean_dataset
from domain.pandas_approach.divergence import find_divergences
from domain.pandas_approach.rsi import rsi

WIDTH = 90


def main() -> int:
    start_time = time.perf_counter()
    args = _parse_args()

    print("=" * WIDTH)
    print("EURUSD RSI DIVERGENCE SCAN")
    print("=" * WIDTH)
    print("Source:", args.source)

    dataset = build_clean_dataset(args.source, timeframe="M5", progress=print)
    df = dataset.frame

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

    print(f"\n{len(divergences)} divergence(s) found:")
    print("-" * WIDTH)

    for divergence in divergences:
        print(f"{divergence.kind:<17} {divergence.start_time} -> {divergence.end_time}")

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

    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
