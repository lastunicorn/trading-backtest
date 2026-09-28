#!/usr/bin/env python3
"""Backtest a registered strategy and write its results into an output directory.

    python3 backtest.py --strategy NAME --source output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv --out output/backtest_NAME
    python3 backtest.py --strategy NAME --source data/eurusd/1min --timeframe 15m --out scratch/bt
    python3 backtest.py --strategy NAME --dukascopy-years 2024 2025 --spread-cost --out scratch/bt_duka

`--source` is a pipeline clean CSV (detected by its `datetime` header), a
folder of MT5 exports, or one export. `--dukascopy-years` reads Dukascopy
bid/ask pairs from the folder in `ports/ducascopy/config.py` instead; those
bars are UTC, not broker-server time.

Writes positions.csv, statistics.txt, statistics.csv and run.json into `--out`
(see `application.backtest`), overwriting earlier results there, and prints
the statistics report. Strategies come from `strategies.STRATEGIES`.

Tooling, not a research stage: versionless and freely editable.
"""

from __future__ import annotations

import argparse
import sys
import time

from application.backtest import Backtest
from application.load_historical_data_use_case import load_dukascopy, load_source
from domain.pandas_approach.cost_model import FixedCost, SpreadCost
from domain.pandas_approach.simulation import AmbiguityPolicy, ResolveFrom
from domain.sample_size import SampleSize
from domain.symbol import by_ticker
from strategies import STRATEGIES


def main() -> int:
    started = time.perf_counter()
    args = _parse_args()

    try:
        timeframe = SampleSize.Parse(args.timeframe)
        symbol = by_ticker(args.symbol)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.source is not None:
        source = args.source
        data = load_source(args.source, timeframe, symbol, progress=print)
    else:
        source = f"Dukascopy {', '.join(map(str, args.dukascopy_years))}"
        data = load_dukascopy(args.dukascopy_years, timeframe, symbol, progress=print)

    cost = SpreadCost(commission_pips=args.commission_pips) if args.spread_cost else FixedCost(pips=args.cost_pips)

    backtest = Backtest(
        strategy=STRATEGIES[args.strategy](),
        data=data,
        cost=cost,
        ambiguity=AmbiguityPolicy(args.ambiguity),
        resolve_from=ResolveFrom(args.resolve_from),
        splits=not args.no_splits,
    )
    result = backtest.run()
    result.run_info["source"] = str(source)

    print()
    print(result.report())
    for path in result.write(args.out):
        print(f"Wrote {path}")

    print(f"\nExecution time: {time.perf_counter() - started:.2f}s")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])

    parser.add_argument("--strategy", required=True, choices=sorted(STRATEGIES),
        help="registered strategy name (strategies.STRATEGIES)")

    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--source",
        help="pipeline clean CSV, folder of MT5 exports, or one MT5 export")
    where.add_argument("--dukascopy-years", type=int, nargs="+", metavar="YEAR",
        help="read Dukascopy bid/ask pairs for these years instead of --source")

    parser.add_argument("--out", required=True,
        help="output directory for the result files (overwritten)")

    parser.add_argument("--timeframe", default="5m",
        help="bar size to backtest on, e.g. 5m, 15m, 1h (default: 5m)")

    parser.add_argument("--symbol", default="EURUSD",
        help="symbol ticker, for pip size and price precision (default: EURUSD)")

    parser.add_argument("--cost-pips", type=float, default=1.7,
        help="fixed round-trip cost per trade in pips (default: 1.7, the pipeline's COST_PIPS)")

    parser.add_argument("--spread-cost", action="store_true",
        help="charge each bar's spread instead of --cost-pips (needs a spread column)")

    parser.add_argument("--commission-pips", type=float, default=0.0,
        help="with --spread-cost: flat commission added per trade (default: 0)")

    parser.add_argument("--ambiguity", default=AmbiguityPolicy.EXCLUDE.value,
        choices=[policy.value for policy in AmbiguityPolicy],
        help="a bar touching both SL and TP: exclude it, or assume one level (default: exclude)")

    parser.add_argument("--resolve-from", default=ResolveFrom.NEXT_BAR.value,
        choices=[start.value for start in ResolveFrom],
        help="first bar SL/TP are checked on (default: next-bar)")

    parser.add_argument("--no-splits", action="store_true",
        help="skip the discovery/validation/test breakdown")

    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
