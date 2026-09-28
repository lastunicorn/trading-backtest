"""Run a strategy over historical data and report how its trades did.

    from application.backtest import Backtest

    result = Backtest(strategy, data).run()     # no I/O
    result.statistics.loc["all", "win_rate_pct"]
    result.write("output/backtest_my_strategy")  # positions.csv, statistics.txt/.csv, run.json

`run()` goes strategy -> open positions -> `simulate_positions` -> costs ->
per-trade P&L -> discovery/validation/test split -> statistics, and returns
all of it. Writing is a separate step, so a notebook or a test can use the
numbers without touching the disk.

The output directory gets four files:

    positions.csv    one row per trade: entry, levels, how it closed, P&L, split
    statistics.txt   the human report -- read this first
    statistics.csv   the same numbers, one row per split, for diffing runs
    run.json         provenance: strategy + parameters, data, simulation settings, git commit
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from domain.pandas_approach.cost_model import CostModel, FixedCost
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import positions_to_frame
from domain.pandas_approach.simulation import AmbiguityPolicy, ResolveFrom, simulate_positions
from domain.pandas_approach.splits import Split, assign_splits, split_dates
from domain.pandas_approach.statistics import statistics_by_split
from domain.pandas_approach.trade_results import trade_results
from domain.pandas_approach.trading_strategy import TradingStrategy

__all__ = ["Backtest", "BacktestResult"]

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Backtest:
    """One strategy, one dataset, one set of simulation rules."""

    strategy: TradingStrategy
    data: HistoricalData
    cost: CostModel = field(default_factory=FixedCost)
    ambiguity: AmbiguityPolicy = AmbiguityPolicy.EXCLUDE
    resolve_from: ResolveFrom = ResolveFrom.NEXT_BAR
    # Report per discovery/validation/test split as well as overall.
    splits: bool = True

    def run(self) -> BacktestResult:
        positions = self.strategy.generate_positions(self.data)
        simulate_positions(self.data, positions, ambiguity=self.ambiguity, resolve_from=self.resolve_from)

        trades = positions_to_frame(positions)
        trades = trade_results(trades, self.data.symbol, self.cost.cost_pips(trades, self.data))
        trades = trades.sort_values("open_dt", kind="stable").reset_index(drop=True)

        if self.splits:
            by_date = split_dates(self.strategy.split_days(self.data))
            trades["split"] = assign_splits(trades["open_dt"], by_date)

        return BacktestResult(
            trades=trades,
            statistics=statistics_by_split(trades),
            run_info=self._run_info(len(trades)),
            price_decimals=self.data.symbol.price_decimals,
        )

    def _run_info(self, trade_count: int) -> dict:
        data = self.data
        return {
            "created": datetime.now().isoformat(timespec="seconds"),
            "strategy": {
                "name": self.strategy.name,
                "class": f"{type(self.strategy).__module__}.{type(self.strategy).__qualname__}",
                "parameters": self.strategy.parameters(),
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
                    "class": type(self.cost).__name__,
                    **(asdict(self.cost) if is_dataclass(self.cost) else {}),
                },
                "ambiguity": self.ambiguity.value,
                "resolve_from": self.resolve_from.value,
                "splits": self.splits,
            },
            "trades": trade_count,
            "git": _git_state(),
        }


@dataclass
class BacktestResult:
    """Everything a run produced. `run_info` is open for callers to add to (e.g. the data source)."""

    trades: pd.DataFrame
    statistics: pd.DataFrame
    run_info: dict
    price_decimals: int = 5

    def write(self, out_dir) -> list[Path]:
        """Write the four result files into `out_dir` (created if needed); returns their paths."""
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)

        paths = [out / "positions.csv", out / "statistics.txt", out / "statistics.csv", out / "run.json"]
        self._rounded_trades().to_csv(paths[0], index=False)
        paths[1].write_text(self.report(), encoding="utf-8")
        self.statistics.to_csv(paths[2], index_label="split")
        paths[3].write_text(json.dumps(self.run_info, indent=2, default=str) + "\n", encoding="utf-8")
        return paths

    def report(self) -> str:
        """The human-readable statistics report."""
        info = self.run_info
        data = info["data"]
        sim = info["simulation"]
        cost = {k: v for k, v in sim["cost_model"].items() if k != "class"}

        lines = [
            "=" * 78,
            f"BACKTEST -- {info['strategy']['name']}",
            "=" * 78,
            f"Parameters:  {_describe(info['strategy']['parameters'])}",
            f"Data:        {data['symbol']} {data['timeframe']}, {data['bars']:,} bars, "
            f"{data['first_bar']} -> {data['last_bar']} ({data['timezone']})",
        ]
        if "source" in info:
            lines.append(f"Source:      {info['source']}")
        lines += [
            f"Costs:       {sim['cost_model']['class']}({_describe(cost)}) per trade, net of every P&L figure",
            f"Simulation:  ambiguous bars {sim['ambiguity']}, SL/TP checked from {sim['resolve_from']}",
            f"Created:     {info['created']}   git {info['git']['commit'] or 'n/a'}"
            + (" (uncommitted changes)" if info["git"]["dirty"] else ""),
            "",
            "A win is net_pips > 0 after costs. Ambiguous trades are counted but carry no P&L.",
            "",
        ]

        table = self.statistics
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

    def _rounded_trades(self) -> pd.DataFrame:
        prices = {column: self.price_decimals for column in ("open_price", "sl", "tp", "close_price")}
        pips = {column: 2 for column in ("gross_pips", "cost_pips", "net_pips", "risk_pips")}
        return self.trades.round({**prices, **pips, "net_r": 3, "duration_min": 1})


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
