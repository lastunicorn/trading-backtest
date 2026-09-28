"""Run a backtest and record it: provenance, the human report, the result files.

    from application.run_backtest_use_case import run_backtest

    run = run_backtest(Backtest(strategy, data), "output/backtest_my_strategy", source="EURUSD_M5_CLEAN.csv")
    print(run.report)
    run.result.statistics      # the domain result, as `Backtest.run()` returned it

`domain.pandas_approach.backtest.Backtest` computes; this module does what
domain must not: reads the clock and git for provenance, and writes files.
The output directory gets four files:

    positions.csv    one row per trade: entry, levels, how it closed, P&L, split
    statistics.txt   the human report -- read this first
    statistics.csv   the same numbers, one row per split, for diffing runs
    run.json         provenance: strategy + parameters, data, simulation settings, git commit

The pieces (`build_run_info`, `format_report`, `write_results`) are public so a
notebook can build a report without writing anything.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path

from domain.pandas_approach.backtest import Backtest, BacktestResult
from domain.pandas_approach.splits import Split

__all__ = ["BacktestRun", "build_run_info", "format_report", "run_backtest", "write_results"]

_REPO_ROOT = Path(__file__).resolve().parent.parent


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
                "class": type(backtest.cost).__name__,
                **(asdict(backtest.cost) if is_dataclass(backtest.cost) else {}),
            },
            "ambiguity": backtest.ambiguity.value,
            "resolve_from": backtest.resolve_from.value,
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
        f"Simulation:  ambiguous bars {sim['ambiguity']}, SL/TP checked from {sim['resolve_from']}",
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
    paths[3].write_text(json.dumps(run_info, indent=2, default=str) + "\n", encoding="utf-8")
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
