"""Formats a backtest's results and writes them into a folder as four files.

    from ports.backtest_result_access import RunProvenance, format_report, write_results

    provenance = RunProvenance(created=now(), git=git_commit(), source="data/eurusd/1min (metatrader)")
    paths = write_results(result, provenance, "output/my_run")   # overwrites
    print(format_report(result, provenance))                      # statistics.txt's text, for the console

The `BacktestResult` (domain) says what ran, on what, under which rules and
what it produced; the `RunProvenance` adds what only the caller knows: when,
from which commit, on which source files, under which name. How all of it
looks on disk is decided here, and only here:

    positions.csv    one row per trade: entry, levels, how it closed, P&L, split
    statistics.txt   the human report (`format_report`) -- read this first
    statistics.csv   the same numbers, one row for all trades plus one per split, for diffing runs
    run.json         provenance (`run_info`): strategy + parameters, data, simulation settings, git commit

The formats are specified in doc/architecture/ports/backtest-result-store.md.
pandas is used only through the result's own frames (`round`, `to_csv`).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, time as clock_time
from pathlib import Path

from domain.market_data.broker_clock import timezone_name
from domain.backtesting.backtest import BacktestResult
from domain.backtesting.splits import SplitMode
from domain.market_data.trading_session import SESSIONS, TradingSession
from ports.run_environment import GitCommit

__all__ = ["RunProvenance", "format_report", "run_info", "write_results"]

# Calendar splits have one row per period, too many for a column each: their
# table is transposed and shows these metrics only (statistics.csv has them all).
_PERIOD_SPLITS = {SplitMode.MONTHLY: "months", SplitMode.YEARLY: "years"}
_PERIOD_REPORT_METRICS = (
    "trades", "win_rate_pct", "total_net_pips", "total_net_r", "profit_factor", "expectancy_r",
    "max_drawdown_pips",
)


@dataclass(frozen=True)
class RunProvenance:
    """What a run's record holds beyond its `BacktestResult`: what only the caller knows.

    `created` and `git` come from `ports.run_environment`. `source` says where
    the bars were read from. `strategy_name` is the name the strategy is
    reported under: the CLI passes the config's `strategy.name` (the
    `STRATEGIES` key), so a run's record names the strategy the way its config
    does; without it, the strategy's own `name` (its class name by default).
    """

    created: datetime
    git: GitCommit
    source: str | None = None
    strategy_name: str | None = None


def write_results(result: BacktestResult, provenance: RunProvenance, out_dir) -> list[Path]:
    """Write the four result files into `out_dir` (created if needed, files overwritten); returns their paths.

    Prices in positions.csv are rounded to the symbol's precision, pips to 2 decimals.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = [out / "positions.csv", out / "statistics.txt", out / "statistics.csv", out / "run.json"]
    _rounded_trades(result).to_csv(paths[0], index=False)
    paths[1].write_text(format_report(result, provenance), encoding="utf-8")
    result.statistics.to_csv(paths[2], index_label="split")
    paths[3].write_text(json.dumps(run_info(result, provenance), indent="\t", default=str) + "\n", encoding="utf-8")
    return paths


def run_info(result: BacktestResult, provenance: RunProvenance) -> dict:
    """The content of `run.json`: what ran, on what, under which rules, from which commit."""
    data = result.data
    strategy = result.strategy
    info = {
        "created": _created(provenance),
        "strategy": {
            "name": _strategy_name(result, provenance),
            "class": f"{type(strategy).__module__}.{type(strategy).__qualname__}",
            "parameters": _parameters(result),
        },
        "data": {
            "symbol": data.symbol.ticker,
            "timeframe": str(data.timeframe),
            "timezone": str(data.timezone),
            "first_bar": data.first_bar.isoformat(),
            "last_bar": data.last_bar.isoformat(),
            "bars": data.bars,
        },
        "simulation": {
            "cost_model": {"class": type(result.cost_model).__name__, **result.cost_model.parameters()},
            "ambiguity_policy": result.ambiguity_policy.value,
        },
        "splits": result.splits.value,
        "trades": len(result.trades),
        "git": asdict(provenance.git),
    }
    if provenance.source is not None:
        info["source"] = provenance.source
    if result.notes:
        info["notes"] = list(result.notes)
    return info


def format_report(result: BacktestResult, provenance: RunProvenance) -> str:
    """The human-readable statistics report (`statistics.txt`)."""
    data = result.data
    git = provenance.git

    lines = [
        "=" * 78,
        f"BACKTEST -- {_strategy_name(result, provenance)}",
        "=" * 78,
        f"Parameters:  {_describe(_parameters(result))}",
        f"Data:        {data.symbol.ticker} {data.timeframe}, {data.bars:,} bars, "
        f"{data.first_bar.isoformat()} -> {data.last_bar.isoformat()} ({data.timezone})",
    ]
    if provenance.source is not None:
        lines.append(f"Source:      {provenance.source}")
    lines += [
        f"Costs:       {type(result.cost_model).__name__}({_describe(result.cost_model.parameters())}) per trade, "
        "net of every P&L figure",
        f"Simulation:  ambiguous bars {result.ambiguity_policy.value}",
        f"Created:     {_created(provenance)}   git {git.commit or 'n/a'}"
        + (" (uncommitted changes)" if git.dirty else ""),
        "",
        "A win is net_pips > 0 after costs. Ambiguous trades are counted but carry no P&L.",
        "",
    ]

    if result.splits in _PERIOD_SPLITS:
        lines += _period_table(result.statistics)
        lines += ["", _period_verdict(result)]
    else:
        lines += _split_table(result.statistics)
        if result.verdict is not None and result.verdict.splits:
            lines += ["", _split_verdict(result)]

    if result.notes:
        lines += ["", "Notes:", *(f"- {note}" for note in result.notes)]

    return "\n".join(lines) + "\n"


def _rounded_trades(result: BacktestResult):
    """The trades as positions.csv holds them: prices to the symbol's precision, pips to 2 decimals."""
    prices = {column: result.data.symbol.price_decimals for column in ("open_price", "sl", "tp", "close_price")}
    pips = {column: 2 for column in ("gross_pips", "cost_pips", "net_pips", "risk_pips")}
    return result.trades.round({**prices, **pips, "net_r": 3, "duration_min": 1})


def _created(provenance: RunProvenance) -> str:
    return provenance.created.isoformat(timespec="seconds")


def _strategy_name(result: BacktestResult, provenance: RunProvenance) -> str:
    return provenance.strategy_name if provenance.strategy_name is not None else result.strategy.name


def _parameters(result: BacktestResult) -> dict:
    return {key: _parameter_text(value) for key, value in result.strategy.parameters().items()}


def _parameter_text(value):
    """A strategy parameter as `run.json` records it, in the spelling a config reads back where there is one.

    A timezone-aware time gets its zone's name ("08:00:00 Europe/London"):
    `str()` of a time on an IANA zone drops the zone. A standard
    `TradingSession` is its `SESSIONS` name ("London"); any other one, its
    bounds and name.
    """
    if isinstance(value, clock_time) and value.tzinfo is not None:
        return f"{value.replace(tzinfo=None)} {timezone_name(value.tzinfo)}"
    if isinstance(value, TradingSession):
        if SESSIONS.get(value.name) == value:
            return value.name
        return {"start_time": _parameter_text(value.start_time), "end_time": _parameter_text(value.end_time),
                "name": value.name}
    return value


def _split_table(table) -> list[str]:
    """One row per metric, one column per split ("all" first)."""
    width = max(len(name) for name in table.columns)
    lines = [f"{'':<{width}}  " + "".join(f"{split:>12}" for split in table.index)]
    lines.append("-" * (width + 2 + 12 * len(table.index)))
    for metric in table.columns:
        cells = "".join(f"{_format(metric, table.loc[split, metric]):>12}" for split in table.index)
        lines.append(f"{metric:<{width}}  {cells}")
    return lines


def _period_table(table) -> list[str]:
    """One row per split ("all" first), one column per `_PERIOD_REPORT_METRICS` metric."""
    width = max(len(split) for split in table.index)
    widths = [max(len(metric), 10) for metric in _PERIOD_REPORT_METRICS]
    lines = [f"{'':<{width}}" + "".join(f"  {metric:>{w}}" for metric, w in zip(_PERIOD_REPORT_METRICS, widths))]
    lines.append("-" * len(lines[0]))
    for split in table.index:
        cells = "".join(f"  {_format(metric, table.loc[split, metric]):>{w}}"
                        for metric, w in zip(_PERIOD_REPORT_METRICS, widths))
        lines.append(f"{split:<{width}}{cells}")
    return lines


def _split_verdict(result: BacktestResult) -> str:
    verdict = result.verdict
    return (f"Net positive in every split ({', '.join(verdict.splits)}): "
            f"{'yes' if verdict.holds_in_every_split else 'no'}")


def _period_verdict(result: BacktestResult) -> str:
    verdict = result.verdict
    return (f"Net positive in {len(verdict.net_positive)} of {len(verdict.traded)} {_PERIOD_SPLITS[result.splits]} "
            f"with trades ({len(verdict.splits) - len(verdict.traded)} without)")


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
