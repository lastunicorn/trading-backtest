#!/usr/bin/env python3
"""Backtest a registered strategy and write its results into an output directory.

    python3 backtest.py --strategy NAME --source output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv --out output/backtest_NAME
    python3 backtest.py --strategy NAME --source data/eurusd/1min --timeframe 15m --out scratch/bt
    python3 backtest.py --strategy NAME --dukascopy-years 2024 2025 --spread-cost --out scratch/bt_duka

`--source` is a pipeline clean CSV (detected by its `datetime` header), a
folder of MT5 exports, or one export. `--dukascopy-years` reads Dukascopy
bid/ask pairs from the folder in `ports/ducascopy/config.py` instead; those
bars are UTC, not broker-server time.

Writes four files into `--out`, overwriting earlier results there, and prints
the statistics report. Strategies come from `strategies.STRATEGIES`.

    positions.csv    one row per trade: entry, levels, how it closed, P&L, split
    statistics.txt   the human report -- read this first
    statistics.csv   the same numbers, one row per split, for diffing runs
    run.json         provenance: strategy + parameters, data, simulation settings, git commit

`domain.pandas_approach.backtest.Backtest` computes; this script does what
domain must not: reads the clock and git for provenance, and writes files.
`run_backtest` and the steps it chains (`build_run_info`, `format_report`,
`write_results`) are importable, so a notebook can run and record a backtest,
or build a report without writing anything:

    from backtest import run_backtest

    run = run_backtest(Backtest(strategy, data), "output/backtest_my_strategy", source="EURUSD_M5_CLEAN.csv")
    print(run.report)
    run.result.statistics      # the domain result, as `Backtest.run()` returned it

Tooling, not a research stage: versionless and freely editable.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path

from application.load_historical_data_use_case import load_dukascopy, load_source
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, BacktestResult, PositionResolveDelay
from domain.pandas_approach.cost_model import FixedCost, SpreadCost
from domain.pandas_approach.splits import Split
from domain.sample_size import SampleSize
from domain.symbol import Symbol, by_ticker
from strategies import STRATEGIES

_REPO_ROOT = Path(__file__).resolve().parent


def main() -> int:
    started = time.perf_counter()
    args = _parse_args()

    try:
        timeframe = SampleSize.Parse(args.timeframe)
        symbol = by_ticker(args.symbol)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        run = _run(args, timeframe, symbol)
    except (ValueError, FileNotFoundError) as error:
        # Data and strategy that don't fit together (wrong clock, no spread
        # column, missing Dukascopy year): say so plainly, not as a traceback.
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print(run.report)
    for path in run.paths:
        print(f"Wrote {path}")

    print(f"\nExecution time: {time.perf_counter() - started:.2f}s")
    return 0


def _run(args: argparse.Namespace, timeframe: SampleSize, symbol: Symbol) -> BacktestRun:
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
        cost_model=cost,
        ambiguity_policy=AmbiguityPolicy(args.ambiguity),
        position_resolve_delay=PositionResolveDelay(args.resolve_from),
        splits=not args.no_splits,
    )
    return run_backtest(backtest, args.out, source=str(source))


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

    parser.add_argument("--resolve-from", default=PositionResolveDelay.NEXT_BAR.value,
        choices=[start.value for start in PositionResolveDelay],
        help="first bar SL/TP are checked on (default: next-bar)")

    parser.add_argument("--no-splits", action="store_true",
        help="skip the discovery/validation/test breakdown")

    return parser.parse_args()



@dataclass(frozen=True)
class BacktestRun:
    """A recorded backtest: the domain result plus what was written about it."""

    result: BacktestResult
    run_info: dict
    report: str
    paths: list[Path]


def run_backtest(backtest: Backtest, out_dir, *, source: str | None = None) -> BacktestRun:
    """Run `backtest` and write its four result files into `out_dir` (overwriting)."""
    result = backtest.run()
    run_info = build_run_info(backtest, result, source=source)
    report = format_report(result, run_info)
    paths = write_results(result, run_info, report, out_dir, price_decimals=backtest.data.symbol.price_decimals)
    return BacktestRun(result, run_info, report, paths)


def build_run_info(backtest: Backtest, result: BacktestResult, *, source: str | None = None) -> dict:
    """Provenance for `run.json`: what ran, on what, under which rules, from which commit."""
    data = backtest.data
    strategy = backtest.strategy
    info = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "strategy": {
            "name": strategy.name,
            "class": f"{type(strategy).__module__}.{type(strategy).__qualname__}",
            "parameters": strategy.parameters(),
        },
        "data": {
            "symbol": data.symbol.ticker,
            "timeframe": str(data.timeframe),
            "timezone": str(data.timezone),
            "first_bar": data.start_dt.isoformat(),
            "last_bar": data.end_dt.isoformat(),
            "bars": len(data),
        },
        "simulation": {
            "cost_model": {
                "class": type(backtest.cost_model).__name__,
                **(asdict(backtest.cost_model) if is_dataclass(backtest.cost_model) else {}),
            },
            "ambiguity_policy": backtest.ambiguity_policy.value,
            "position_resolve_delay": backtest.position_resolve_delay.value,
            "splits": backtest.splits,
        },
        "trades": len(result.trades),
        "git": _git_state(),
    }
    if source is not None:
        info["source"] = source
    return info


def format_report(result: BacktestResult, run_info: dict) -> str:
    """The human-readable statistics report (`statistics.txt`)."""
    data = run_info["data"]
    sim = run_info["simulation"]
    cost = {k: v for k, v in sim["cost_model"].items() if k != "class"}

    lines = [
        "=" * 78,
        f"BACKTEST -- {run_info['strategy']['name']}",
        "=" * 78,
        f"Parameters:  {_describe(run_info['strategy']['parameters'])}",
        f"Data:        {data['symbol']} {data['timeframe']}, {data['bars']:,} bars, "
        f"{data['first_bar']} -> {data['last_bar']} ({data['timezone']})",
    ]
    if "source" in run_info:
        lines.append(f"Source:      {run_info['source']}")
    lines += [
        f"Costs:       {sim['cost_model']['class']}({_describe(cost)}) per trade, net of every P&L figure",
        f"Simulation:  ambiguous bars {sim['ambiguity_policy']}, SL/TP checked from {sim['position_resolve_delay']}",
        f"Created:     {run_info['created']}   git {run_info['git']['commit'] or 'n/a'}"
        + (" (uncommitted changes)" if run_info["git"]["dirty"] else ""),
        "",
        "A win is net_pips > 0 after costs. Ambiguous trades are counted but carry no P&L.",
        "",
    ]

    table = result.statistics
    width = max(len(name) for name in table.columns)
    lines.append(f"{'':<{width}}  " + "".join(f"{split:>12}" for split in table.index))
    lines.append("-" * (width + 2 + 12 * len(table.index)))
    for metric in table.columns:
        cells = "".join(f"{_format(metric, table.loc[split, metric]):>12}" for split in table.index)
        lines.append(f"{metric:<{width}}  {cells}")

    splits = [split.value for split in Split if split.value in table.index]
    if splits:
        net = table.loc[splits, "total_net_pips"]
        verdict = "yes" if (net > 0).all() else "no"
        lines += ["", f"Net positive in every split ({', '.join(splits)}): {verdict}"]

    return "\n".join(lines) + "\n"


def write_results(result: BacktestResult, run_info: dict, report: str, out_dir, *, price_decimals: int) -> list[Path]:
    """Write the four result files into `out_dir` (created if needed); returns their paths.

    Prices in positions.csv are rounded to `price_decimals` (the symbol's
    precision), pips to 2 decimals.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    prices = {column: price_decimals for column in ("open_price", "sl", "tp", "close_price")}
    pips = {column: 2 for column in ("gross_pips", "cost_pips", "net_pips", "risk_pips")}
    trades = result.trades.round({**prices, **pips, "net_r": 3, "duration_min": 1})

    paths = [out / "positions.csv", out / "statistics.txt", out / "statistics.csv", out / "run.json"]
    trades.to_csv(paths[0], index=False)
    paths[1].write_text(report, encoding="utf-8")
    result.statistics.to_csv(paths[2], index_label="split")
    paths[3].write_text(json.dumps(run_info, indent="\t", default=str) + "\n", encoding="utf-8")
    return paths


def _describe(values: dict) -> str:
    return ", ".join(f"{key}={value}" for key, value in values.items()) or "none"


def _format(metric: str, value) -> str:
    """One statistics cell: counts as integers, the rest to a sensible precision."""
    if isinstance(value, float) and math.isnan(value):
        return "n/a"
    if isinstance(value, float) and math.isinf(value):
        return "inf"
    if metric.endswith("_pct"):
        return f"{value:.1f}%"
    if metric.endswith("_pips"):
        return f"{value:,.1f}"
    if metric == "profit_factor":
        return f"{value:.2f}"
    if metric.endswith("_r"):
        return f"{value:.3f}"
    if metric.endswith("_min"):
        return f"{value:,.0f}"
    return f"{int(value):,}"


def _git_state() -> dict:
    """The repo's HEAD commit and whether the working tree has changes; None when git is unavailable."""
    def git(*args: str) -> str | None:
        try:
            completed = subprocess.run(
                ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, timeout=10, check=True,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return completed.stdout.strip()

    status = git("status", "--porcelain")
    return {"commit": git("rev-parse", "--short", "HEAD"), "dirty": None if status is None else bool(status)}


if __name__ == "__main__":
    raise SystemExit(main())
