#!/usr/bin/env python3
"""Backtest a registered strategy and write its results into an output directory.

    python3 backtest.py backtests/narrow_asia_fade/backtest.json
    python3 backtest.py backtests/narrow_asia_fade          # a folder: reads its backtest.json

The only argument is a JSON config file, or a folder holding one named
`backtest.json`. Every setting lives in the config (read by
`application.load_backtest_config_use_case.load_backtest_config`; see
help/backtest-framework/backtest-config.md); relative paths in it are
resolved against the config file's own folder, not the working directory:

    {
        "strategy": "narrow_asia_fade",
        "data": {
            "source": "../../output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv",
            "format": "clean-csv",
            "symbol": "EURUSD",
            "timeframe": "5m",
            "timezone": "broker"
        },
        "out": "../../output/backtest_narrow_asia_fade",
        "timeframe": "5m",
        "ambiguity": "assume-sl",
        "strategy_parameters": {"rel_vol_min": 1.8, "study_end": "13:00"}
    }

`strategy_parameters` (optional) overrides the strategy's dataclass fields;
the rest keep their defaults. Time fields take "HH:MM" strings (on the data's
clock), timezone-aware ones (`ZonedTime`) "HH:MM <zone>" such as
"08:00 Europe/London" or "10:00 broker". A nullable field also takes null.

`data` describes the bars as they are on disk. `source` (a file or a folder)
and `format` say where they are and how to read them: "metatrader" for MT4/MT5
exports, "dukascopy" for Dukascopy bid/ask pairs (UTC bars, not broker-server
time), "clean-csv" for the research pipeline's clean CSV. `symbol` is
required; `timeframe` (default "1m") is the bar size of the source, which the
root `timeframe` -- the size to backtest on -- must be a whole multiple of.
`timezone` (default "UTC") is the clock the source's timestamps are on: an
IANA name such as "America/New_York", or "broker" for this repo's MT5
broker-server clock (New York + 7h). It labels the bars; nothing is shifted.

Writes four files into `out`, overwriting earlier results there, and prints
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
from datetime import datetime, time as clock_time
from pathlib import Path

from application.load_backtest_config_use_case import cost_model, load_backtest_config
from application.load_historical_data_use_case import SourceFormat, load_source
from domain.broker_clock import timezone_by_name, timezone_name
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, BacktestResult, PositionCloseDelay
from domain.pandas_approach.splits import Split
from domain.sample_size import SampleSize
from domain.symbol import Symbol, by_ticker
from ports.backtest_config_access import CONFIG_FILE_NAME, BacktestConfig
from strategies import STRATEGIES

_REPO_ROOT = Path(__file__).resolve().parent


def main() -> int:
    started = time.perf_counter()
    args = _parse_args()

    try:
        config = load_backtest_config(args.config)
        timeframe = SampleSize.Parse(config.timeframe)
        symbol = by_ticker(config.data.symbol)
    except (ValueError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        run = _run(config, timeframe, symbol)
    except (ValueError, FileNotFoundError) as error:
        # Data and strategy that don't fit together (wrong clock, no spread
        # column, missing source files): say so plainly, not as a traceback.
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print()
    print(run.report)
    for path in run.paths:
        print(f"Wrote {path}")

    print(f"\nExecution time: {time.perf_counter() - started:.2f}s")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "config",
        help=f"backtest config JSON file, or a folder holding one named {CONFIG_FILE_NAME}")
    return parser.parse_args()


def _run(config: BacktestConfig, timeframe: SampleSize, symbol: Symbol) -> BacktestRun:
    source_format = SourceFormat(config.data.format)
    data = load_source(config.data.source, source_format, timeframe, symbol,
                       timezone=timezone_by_name(config.data.timezone), progress=print)

    backtest = Backtest(
        strategy=STRATEGIES[config.strategy](**config.strategy_parameters),
        data=data,
        cost_model=cost_model(config.cost),
        ambiguity_policy=AmbiguityPolicy(config.ambiguity),
        position_resolve_delay=PositionCloseDelay(config.resolve_from),
        splits=config.splits,
    )
    return run_backtest(backtest, config.out, source=f"{config.data.source} ({source_format.value})")


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
            "parameters": {key: _parameter_text(value) for key, value in strategy.parameters().items()},
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


def _parameter_text(value):
    """A strategy parameter as `run.json` records it: a timezone-aware time with its zone's name, else unchanged.

    `str()` of a time on an IANA zone drops the zone; this keeps it, in the
    spelling a config reads back ("08:00:00 Europe/London").
    """
    if isinstance(value, clock_time) and value.tzinfo is not None:
        return f"{value.replace(tzinfo=None)} {timezone_name(value.tzinfo)}"
    return value


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
