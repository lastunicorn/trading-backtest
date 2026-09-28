#!/usr/bin/env python3
"""Backtest a registered strategy and write its results into an output directory.

    python3 backtest.py backtests/narrow_asia_fade/backtest.json
    python3 backtest.py backtests/narrow_asia_fade          # a folder: reads its backtest.json

The only argument is a JSON config file, or a folder holding one named
`backtest.json`. Every setting lives in the config (see `load_config` and
help/backtest-framework/running-a-backtest.md); relative paths in it are
resolved against the config file's own folder, not the working directory:

    {
        "strategy": "narrow_asia_fade",
        "source": "../../output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv",
        "out": "../../output/backtest_narrow_asia_fade",
        "ambiguity": "assume-sl",
        "strategy_parameters": {"rel_vol_min": 1.8, "study_end": "13:00"}
    }

`strategy_parameters` (optional) overrides the strategy's dataclass fields;
the rest keep their defaults. Time fields take "HH:MM" strings.

`source` is a pipeline clean CSV (detected by its `datetime` header), a
folder of MT5 exports, or one export. `dukascopy_years` (instead of `source`)
reads Dukascopy bid/ask pairs from the folder in `ports/ducascopy/config.py`;
those bars are UTC, not broker-server time.

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
import os
import subprocess
import sys
import time
import typing
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, time as clock_time
from pathlib import Path

from application.load_historical_data_use_case import load_dukascopy, load_source
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, BacktestResult, PositionResolveDelay
from domain.pandas_approach.cost_model import FixedCost, SpreadCost
from domain.pandas_approach.splits import Split
from domain.sample_size import SampleSize
from domain.symbol import Symbol, by_ticker
from strategies import STRATEGIES

_REPO_ROOT = Path(__file__).resolve().parent


CONFIG_FILE_NAME = "backtest.json"


def main() -> int:
    started = time.perf_counter()
    args = _parse_args()

    try:
        config = load_config(args.config)
        timeframe = SampleSize.Parse(config.timeframe)
        symbol = by_ticker(config.symbol)
    except (ValueError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        run = _run(config, timeframe, symbol)
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "config",
        help=f"backtest config JSON file, or a folder holding one named {CONFIG_FILE_NAME}")
    return parser.parse_args()


def _run(config: BacktestConfig, timeframe: SampleSize, symbol: Symbol) -> BacktestRun:
    if config.source is not None:
        source = config.source
        data = load_source(config.source, timeframe, symbol, progress=print)
    else:
        source = f"Dukascopy {', '.join(map(str, config.dukascopy_years))}"
        data = load_dukascopy(list(config.dukascopy_years), timeframe, symbol, progress=print)

    cost = SpreadCost(commission_pips=config.commission_pips) if config.spread_cost else FixedCost(pips=config.cost_pips)

    backtest = Backtest(
        strategy=STRATEGIES[config.strategy](**config.strategy_parameters),
        data=data,
        cost_model=cost,
        ambiguity_policy=AmbiguityPolicy(config.ambiguity),
        position_resolve_delay=PositionResolveDelay(config.resolve_from),
        splits=config.splits,
    )
    return run_backtest(backtest, config.out, source=str(source))


@dataclass(frozen=True)
class BacktestConfig:
    """The settings of one CLI run, as read from its JSON config by `load_config`.

    Field names are the JSON keys. `source` and `out` are already resolved
    against the config file's folder. Exactly one of `source` and
    `dukascopy_years` is set. `strategy_parameters` holds the strategy's
    constructor arguments, already converted to its field types (a JSON
    "HH:MM" string becomes a `datetime.time`).
    """

    strategy: str
    out: Path
    source: Path | None = None
    dukascopy_years: tuple[int, ...] | None = None
    timeframe: str = "5m"
    symbol: str = "EURUSD"
    cost_pips: float = 1.7
    spread_cost: bool = False
    commission_pips: float = 0.0
    ambiguity: str = AmbiguityPolicy.EXCLUDE.value
    resolve_from: str = PositionResolveDelay.NEXT_BAR.value
    splits: bool = True
    strategy_parameters: dict[str, object] = field(default_factory=dict)


# The JSON type each config key must have. bool is kept apart from the numbers
# on purpose: `"cost_pips": true` is a mistake, not 1 pip.
_CONFIG_KEY_TYPES = {
    "strategy": str,
    "source": str,
    "dukascopy_years": list,
    "out": str,
    "timeframe": str,
    "symbol": str,
    "cost_pips": float,
    "spread_cost": bool,
    "commission_pips": float,
    "ambiguity": str,
    "resolve_from": str,
    "splits": bool,
    "strategy_parameters": dict,
}


def find_config_file(path) -> Path:
    """`path` itself if it is a file, `path/backtest.json` if it is a folder."""
    path = Path(path)
    if path.is_dir():
        path = path / CONFIG_FILE_NAME
    if not path.is_file():
        raise FileNotFoundError(f"no backtest config at {path}")
    return path


def load_config(path) -> BacktestConfig:
    """Read and validate a backtest config: a JSON file, or a folder holding `backtest.json`.

    Unknown keys, wrong types and invalid choices raise `ValueError` naming the
    file, so a typo fails the run instead of silently falling back to a default.
    """
    file = find_config_file(path)
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{file}: not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"{file}: expected a JSON object, got {type(raw).__name__}")

    def fail(message: str) -> ValueError:
        return ValueError(f"{file}: {message}")

    unknown = sorted(set(raw) - set(_CONFIG_KEY_TYPES))
    if unknown:
        raise fail(f"unknown key(s) {', '.join(unknown)}; allowed: {', '.join(_CONFIG_KEY_TYPES)}")
    for key, value in raw.items():
        if not _has_json_type(value, _CONFIG_KEY_TYPES[key]):
            raise fail(f'"{key}" must be {_JSON_TYPE_NAMES[_CONFIG_KEY_TYPES[key]]}, got {json.dumps(value)}')

    for key in ("strategy", "out"):
        if key not in raw:
            raise fail(f'"{key}" is required')
    if ("source" in raw) == ("dukascopy_years" in raw):
        raise fail('give exactly one of "source" and "dukascopy_years"')

    _check_choice(raw, "strategy", sorted(STRATEGIES), fail)
    _check_choice(raw, "ambiguity", [policy.value for policy in AmbiguityPolicy], fail)
    _check_choice(raw, "resolve_from", [start.value for start in PositionResolveDelay], fail)

    values = dict(raw)
    values["out"] = _relative_to(file, raw["out"])
    if "source" in raw:
        values["source"] = _relative_to(file, raw["source"])
    if "dukascopy_years" in raw:
        years = raw["dukascopy_years"]
        if not years or not all(_has_json_type(year, int) for year in years):
            raise fail(f'"dukascopy_years" must be a non-empty list of years, got {json.dumps(years)}')
        values["dukascopy_years"] = tuple(years)
    for key in ("cost_pips", "commission_pips"):
        if key in raw:
            values[key] = float(raw[key])
    if "strategy_parameters" in raw:
        values["strategy_parameters"] = _strategy_parameters(raw["strategy"], raw["strategy_parameters"], fail)
    return BacktestConfig(**values)


def _strategy_parameters(name: str, raw: dict, fail) -> dict[str, object]:
    """`raw` converted to the field types of strategy `name`, checked by building the strategy once.

    Building it here means an out-of-range value (rejected by the strategy's
    `__post_init__`) fails before any data is loaded, not after.
    """
    strategy_class = STRATEGIES[name]
    types = typing.get_type_hints(strategy_class)
    names = [f.name for f in fields(strategy_class) if f.init] if is_dataclass(strategy_class) else []

    unknown = sorted(set(raw) - set(names))
    if unknown:
        raise fail(f"{name} has no parameter(s) {', '.join(unknown)}; "
                   f"its parameters: {', '.join(names) or 'none'}")

    converted = {}
    for key, value in raw.items():
        expected = types[key]
        if expected is clock_time:
            try:
                converted[key] = clock_time.fromisoformat(value) if isinstance(value, str) else None
            except ValueError:
                converted[key] = None
            if converted[key] is None:
                raise fail(f'strategy parameter "{key}" must be a time "HH:MM", got {json.dumps(value)}')
        elif expected in (int, float, bool, str):
            if not _has_json_type(value, expected):
                raise fail(f'strategy parameter "{key}" must be {_JSON_TYPE_NAMES[expected]}, got {json.dumps(value)}')
            converted[key] = float(value) if expected is float else value
        else:
            raise fail(f'strategy parameter "{key}" has type {expected}, which a JSON config cannot set')

    try:
        strategy_class(**converted)
    except (TypeError, ValueError) as error:
        raise fail(f"invalid strategy_parameters for {name}: {error}") from error
    return converted


def _relative_to(config_file: Path, path: str) -> Path:
    """`path` resolved against the config file's folder, with `..` folded away (symlinks untouched)."""
    return Path(os.path.normpath(config_file.parent / path))


_JSON_TYPE_NAMES = {str: "a string", float: "a number", int: "a whole number", bool: "true or false",
                    list: "a list", dict: "a JSON object"}


def _has_json_type(value, expected: type) -> bool:
    if isinstance(value, bool):
        return expected is bool
    if expected is float:
        return isinstance(value, (int, float))
    return isinstance(value, expected)


def _check_choice(raw: dict, key: str, choices: list[str], fail) -> None:
    if key in raw and raw[key] not in choices:
        raise fail(f'"{key}" is {json.dumps(raw[key])}; choose one of {", ".join(choices)}')


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
