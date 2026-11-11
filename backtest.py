#!/usr/bin/env python3
"""Backtest a registered strategy and write its results into an output directory.

    python3 backtest.py backtests/narrow_asia_fade/backtest.json
    python3 backtest.py backtests/narrow_asia_fade          # a folder: reads its backtest.json

The only argument is a JSON config file, or a folder holding one named
`backtest.json`. Every setting lives in the config (read by
`application.load_backtest_config_use_case.load_backtest_config`; see
doc/backtest-framework/backtest-config.md); relative paths in it are
resolved against the config file's own folder, not the working directory:

    {
        "strategy": {
            "name": "narrow_asia_fade",
            "parameters": {"rel_vol_min": 1.8, "study_end": "13:00"}
        },
        "data_source": {
            "path": "../../data/eurusd/1min",
            "format": "metatrader",
            "symbol": "EURUSD",
            "timeframe": "1m",
            "timezone": "broker"
        },
        "simulation": {
            "timeframe": "5m",
            "ambiguity": "assume-sl",
            "cost": {"commission_pips": 1.7}
        },
        "out": "output",
        "splits": "dvt"
    }

`strategy.name` is a key of `strategies.STRATEGIES`; `strategy.parameters`
(optional) overrides the strategy's dataclass fields, the rest keep their
defaults. Time fields take "HH:MM" strings (on the data's clock),
timezone-aware ones (`ZonedTime`) "HH:MM <zone>" such as "08:00 Europe/London"
or "10:00 broker". A nullable field also takes null.

`data_source` describes the bars as they are on disk. `path` (a file or a
folder) and `format` say where they are and how to read them: "metatrader" for
MT4/MT5 exports, "histdata" for histdata.com downloads (New York time),
"dukascopy" for Dukascopy bid/ask pairs (UTC bars, not broker-server time).
`symbol` is required; `timeframe` (default "1m") is the bar size of the source, which
`simulation.timeframe` -- the size to backtest on -- must be a whole multiple of.
`timezone` (default "UTC") is the clock the source's timestamps are on: an
IANA name such as "America/New_York", "broker" for this repo's MT5
broker-server clock (New York + 7h), or "histdata" for histdata.com downloads
(New York's clock, on the EU daylight-saving dates from 2019). It labels the
bars; nothing is shifted.

`simulation` holds the rules the positions are traded under: `timeframe`
(default "5m"), `ambiguity` (default "exclude") and `cost` (`spread`,
`commission_pips`; no cost by default). Where SL/TP checking starts is not a
setting: each position's `entry_fill`, set by the strategy, decides it.

`splits` (default "none") breaks the statistics down by group as well as
overall: "dvt" for the 60/20/20 discovery / validation / test cut, "monthly"
or "yearly" for one group per calendar month or year.

Writes four files into `out`, overwriting earlier results there, and prints
the statistics report. Strategies come from `strategies.STRATEGIES`.

    positions.csv    one row per trade: entry, levels, how it closed, P&L, split
    statistics.txt   the human report -- read this first
    statistics.csv   the same numbers, one row for all trades plus one per split, for diffing runs
    run.json         provenance: strategy + parameters, data, simulation settings, git commit

`domain.pandas_approach.backtest.Backtest` computes the result and describes
the run; `ports.backtest_result_access` formats it and writes the files. This
script wires them together, adding the provenance only it can know: the clock
and git (`ports.run_environment`), the source and the config's strategy name.
`run_backtest` is importable, so a notebook can run and record a backtest:

    from backtest import run_backtest

    run = run_backtest(Backtest(strategy, data), "output/backtest_my_strategy", source="data/eurusd/1min",
                       strategy_name="my_strategy")   # optional; default the strategy's own `name`
    print(run.report)
    run.result.statistics      # the domain result, as `Backtest.run()` returned it

To build the report without writing anything, call
`ports.backtest_result_access.format_report(result, provenance)` on a result
and a `RunProvenance`.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from application.build_clean_dataset_use_case import NoUsableSourceFilesError
from application.load_backtest_config_use_case import cost_model, load_backtest_config
from application.load_historical_data_use_case import SourceFormat, load_source
from domain.broker_clock import timezone_by_name
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, BacktestResult
from domain.pandas_approach.splits import SplitMode
from domain.sample_size import SampleSize
from domain.symbol import Symbol, get_symbol_by_ticker
from ports import run_environment
from ports.backtest_config_access import CONFIG_FILE_NAME, BacktestConfig
from ports.backtest_result_access import RunProvenance, format_report, write_results
from ports.run_environment import GitCommit
from strategies import STRATEGIES


def main() -> int:
    started = time.perf_counter()
    args = _parse_args()

    try:
        config = load_backtest_config(args.config)
        timeframe = SampleSize.Parse(config.simulation.timeframe)
        symbol = get_symbol_by_ticker(config.data_source.symbol)
    except (ValueError, FileNotFoundError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    try:
        run = _run(config, timeframe, symbol)
    except (ValueError, FileNotFoundError, NoUsableSourceFilesError) as error:
        # Data and strategy that don't fit together (wrong clock, no spread
        # column), missing or unreadable source files: say so plainly, not as
        # a traceback.
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
    source_format = SourceFormat(config.data_source.format)
    data = load_source(config.data_source.path, source_format, timeframe, symbol,
                       timezone=timezone_by_name(config.data_source.timezone), progress=print)

    backtest = Backtest(
        strategy=STRATEGIES[config.strategy.name](**config.strategy.parameters),
        data=data,
        cost_model=cost_model(config.simulation.cost),
        ambiguity_policy=AmbiguityPolicy(config.simulation.ambiguity),
        splits=SplitMode(config.splits),
    )
    return run_backtest(backtest, config.out, source=f"{config.data_source.path} ({source_format.value})",
                        strategy_name=config.strategy.name)


@dataclass(frozen=True)
class BacktestRun:
    """A recorded backtest: the domain result, the provenance recorded with it, the files written."""

    result: BacktestResult
    provenance: RunProvenance
    paths: list[Path]

    @property
    def report(self) -> str:
        """The statistics report: the text of statistics.txt."""
        return format_report(self.result, self.provenance)


def run_backtest(
    backtest: Backtest,
    out_dir,
    *,
    source: str | None = None,
    strategy_name: str | None = None,
    now: Callable[[], datetime] = run_environment.now,
    git_commit: Callable[[], GitCommit] = run_environment.git_commit,
) -> BacktestRun:
    """Run `backtest` and write its four result files into `out_dir` (overwriting).

    `source` and `strategy_name` are recorded as `RunProvenance` describes.
    `now` and `git_commit` read the clock and the repo (`ports.run_environment`);
    pass fakes to make the record deterministic.
    """
    result = backtest.run()
    provenance = RunProvenance(
        created=now(),
        git=git_commit(),
        source=source,
        strategy_name=strategy_name)
    return BacktestRun(result, provenance, write_results(result, provenance, out_dir))


if __name__ == "__main__":
    raise SystemExit(main())
