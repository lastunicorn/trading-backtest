# Application Blueprint

A description of the application that doesn't depend on Python: its domain entities, ports, use cases, plugins (strategies), user interface and file formats, written so the application can be rebuilt in another language and behave the same. It describes **behaviour**, not implementation: pandas data frames, vectorised numpy and Python's class layout are the current implementation's choices, not part of the contract. Each section names the Python module it describes, for when a detail is missing here.

How the *Python* code is organised (folders, import rules, where new code goes) is a different question, answered by [doc/architecture.md](../architecture.md).

## Contents

| Page | Covers |
|---|---|
| [conventions.md](conventions.md) | **Read first.** Type notation, naming, errors, progress reporting, and the rules about market data that hold everywhere (bars, bid prices, units, clocks) |
| [domain-market-data.md](domain-market-data.md) | Domain: `SampleSize`, `Symbol`, clocks, `TimeWindow`, `TradingSession`, `Bar`, bar table operations, `HistoricalData` |
| [domain-backtest.md](domain-backtest.md) | Domain: `Position`, cost models, the backtest and its exit rules, trade results, splits, statistics |
| [domain-indicators.md](domain-indicators.md) | Domain: RSI and divergence detection |
| [plugins/](plugins/README.md) | The strategy contract, the registry and parameters; one page per strategy |
| [ports/](ports/README.md) | The seven ports, one page each: actions, errors, DTOs, and the format libraries behind the bar ports |
| [use-cases/](use-cases/README.md) | The nine use cases, one page each: input, output, steps, errors |
| [ui/](ui/README.md) | The five CLIs, one page each: arguments, validation at UI level, output; shared presentation |
| [external-formats.md](external-formats.md) | Every file read or written: bar data, the backtest config, the result files |

---

## The application in one page

A backtesting toolkit for intraday FX strategies (mostly EURUSD). It reads M1 bar data from three sources (MetaTrader exports, histdata.com downloads, Dukascopy bid/ask pairs), each on its own clock, and:

- **backtests** a registered strategy under one fixed set of simulation rules, writing its trades, statistics and provenance (`backtest`);
- **inspects and converts** bar data: display, shift clocks, resample, write a MetaTrader CSV (`read_csv`);
- computes **per-day session OHLC** (`calculate_daily_sessions`);
- **scans for RSI divergences** (`rsi_divergence`);
- **lists the known symbols** (`show_symbols`).

### Components

```
┌──────────────────────────────────────────────────┐
│ UI           5 CLIs, shared presentation         │
└────────────────────────┬─────────────────────────┘
                         ▼
┌──────────────────────────────────────────────────┐
│ Use cases    9 tasks                             │
└────────┬───────────────────┬───────────────┬─────┘
         ▼                   ▼               │
┌──────────────────┐ ┌─────────────────┐     │
│ Ports            │ │ Plugins         │     │
│ files, config,   │ │ 5 strategies +  │     │
│ clock, git       │ │ their registry  │     │
│   └► format libs │ │                 │     │
└────────┬─────────┘ └────────┬────────┘     │
         ▼ entities only      ▼              ▼
┌──────────────────────────────────────────────────┐
│ Domain       concepts and calculations, no I/O   │
└──────────────────────────────────────────────────┘
```

| Component | Responsible for | May depend on |
|---|---|---|
| **Domain** | what the data means and every calculation: bars, clocks, sessions, positions, the exit rules, costs, statistics | nothing |
| **Plugins** | deciding where strategies enter | Domain |
| **Ports** | reading and writing outside the process: data files, the config, result files, the clock, git | the domain types they parse into or write out; format libraries |
| **Format libraries** | a file format, knowing nothing of this application | nothing in the application |
| **Use cases** | wiring ports, domain and plugins into a task | ports (as interfaces), Domain, Plugins |
| **UI** | arguments in, results out, exit codes | use cases; Domain (to parse arguments into domain types and format results) |

Everything points towards the domain, which can therefore be tested without a file, a clock or a terminal.

### A backtest, end to end

1. The `backtest` CLI passes a config path to [RunBacktestFromConfig](use-cases/run-backtest-from-config.md).
2. [LoadBacktestConfig](use-cases/load-backtest-config.md) reads the JSON and checks every value against the registry, the symbols, the clocks and the strategy's own parameter rules.
3. [LoadHistoricalData](use-cases/load-historical-data.md) reads the bars with the format's port, merges files, drops duplicate timestamps, resamples and converts the spread to pips: a validated `HistoricalData`.
4. The strategy [generates open positions](plugins/README.md#the-plugin-contract-tradingstrategy); the backtest [closes each one](domain-backtest.md#the-exit-rules), charges costs, computes per-trade results and statistics, overall and per split.
5. [RecordBacktest](use-cases/record-backtest.md) adds provenance (clock, git), formats the report and writes `positions.csv`, `statistics.txt`, `statistics.csv` and `run.json`.

---

## Rebuilding the application from this blueprint

A workable order: [conventions](conventions.md) → [market data](domain-market-data.md) → [backtest domain](domain-backtest.md) → one strategy ([`orb_break_entry`](plugins/orb-break-entry.md) is the simplest) → [ports](ports/README.md) with [external formats](external-formats.md) → [use cases](use-cases/README.md) → [UI](ui/README.md) → the remaining strategies and [indicators](domain-indicators.md).

To check a rewrite, run the same config on the same data in both versions and compare `positions.csv` and `statistics.csv` (and `statistics.txt`, apart from its `Created` line). The Python tests under `tests/` mirror the source layout, one file per function, and are executable examples of each item's behaviour; `tests/strategies/session_breakout/_script_trades.py` holds the trades the `session_breakout` strategy must reproduce exactly.

### Where a rewrite should differ from the Python code

The blueprint describes what the Python code does. In a few places it is not what the code *should* do, and the page says so:

| Page | Recommendation |
|---|---|
| [ports/backtest-result-store.md](ports/backtest-result-store.md) | Writing the result files lives in the `backtest` entry script; put it behind a port like the others. |
| [use-cases/prepare-bars.md](use-cases/prepare-bars.md), [scan-rsi-divergences.md](use-cases/scan-rsi-divergences.md) | `read_csv`'s pipeline and `rsi_divergence`'s scan sit in the CLIs' `main()`; give them use-case functions. |
| [domain-market-data.md §7](domain-market-data.md#7-bar-table-operations) | `resample_ohlc` also accepts raw pandas rules; take a `SampleSize` only. |
| [ui/README.md](ui/README.md#common-behaviour) | Some use-case errors end in a stack trace; report every one as an `ERROR:` line. |
| [ui/calculate-daily-sessions.md](ui/calculate-daily-sessions.md), [rsi-divergence.md](ui/rsi-divergence.md) | `calculate_daily_sessions` defaults to a machine-specific folder and validates `--source-timezone` differently from `read_csv`; `rsi_divergence` doesn't range-check its numbers. |

### Scope

Covered: everything the five CLIs do, and the Python API a notebook uses to run and record a backtest. Left out: the legacy bar-stream code nothing uses ([domain-market-data.md §9](domain-market-data.md#9-legacy-not-needed-for-a-rewrite)), `temp/` (the Pine source of the RSI indicator, a reference), the tests themselves and the development environment.

### Format of these pages

Plain Markdown, made precise by a fixed type notation ([conventions.md](conventions.md#1-type-notation)), the same layout for every item (properties, actions, errors) and the exact wire names of every key, column and flag. Markdown reads well, diffs well in reviews and works as input to people and code assistants alike. Two additions would pay off if a rewrite actually starts, and are not built yet:

- **A JSON Schema** for the backtest config and `run.json`: the two external contracts where a machine-readable schema gives validation and editor completion for free, in any language.
- **A conformance kit**: a few small bar files with the `positions.csv` and `statistics.csv` the Python version produces for a config each, so a rewrite can be checked mechanically rather than against private data.

### Keeping it in sync

When a behaviour, a public action, a file format, a config key or a CLI flag changes, update the page here that describes it, along with the user documentation in `doc/backtest-framework/` and `doc/strategies/`.
