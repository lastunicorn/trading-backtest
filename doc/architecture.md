# Architecture

How the code is split into components, what each one is responsible for, and which component may depend on which. Read this before adding a module or moving code between folders.

This page is about the Python code's layout. What the application does, independent of the language (its entities, ports, use cases, strategies, UI and file formats), is the blueprint in [architecture/](architecture/README.md).

## Contents

1. [The components](#1-the-components)
2. [Import rules](#2-import-rules)
3. [Inside an entry script](#3-inside-an-entry-script)
4. [Where does new code go?](#4-where-does-new-code-go)
5. [Inside the domain](#5-inside-the-domain)

---

## 1. The components

The application has seven components. Six are packages; the seventh is the set of entry scripts at the repo root.

```
                   ┌───────────────────────────┐
                   │ entry scripts (repo root) │
                   └───┬────────┬──────────┬───┘
           ┌───────────┘        │          └────────┐
           ▼                    ▼                   ▼
    ┌─────────────┐       ┌────────────┐        ┌────────┐
    │ application │──────►│ strategies │        │   ui   │
    └──┬───────┬──┘       └─────┬──────┘        └───┬────┘
       ▼       │                │                   │
   ┌───────┐   │                │                   │
   │ ports │───┼────────────────┼───────────────────┼───────►┌──────┐
   └───┬───┘   │                │                   │        │ libs │
       │ allowed names          │                   │        └──────┘
       ▼       ▼                ▼                   ▼
   ┌───────────────────────────────────────────────────────┐
   │                         domain                        │
   └───────────────────────────────────────────────────────┘
```

*An arrow means "may import". Entry scripts may also import `ports` and `domain` directly (not drawn). Everything points towards `domain/`, which imports nothing in the repo. `libs/` imports nothing in the repo either, and only `ports/` imports it.*

| Component | Where | Responsible for |
|---|---|---|
| **Entry scripts** | `*.py` at the repo root | one use case each: its UI and its steps |
| **Application** | `application/` | orchestration shared by use cases, or too big for one script |
| **Ports** | `ports/` | talking to external resources: files, config, the clock, git |
| **Libraries** | `libs/` | reusable, application-neutral code for a file format, used by ports |
| **Domain** | `domain/` | the concepts and the calculations; no I/O |
| **Strategies** | `strategies/` | the `TradingStrategy` plugins and their registry |
| **UI** | `ui/` | UI logic reused by more than one entry script |

### Entry scripts

One script per use case, at the repo root: `backtest.py`, `read_csv.py`, `rsi_divergence.py`, `calculate_daily_sessions.py`, `show_symbols.py`. They must stay at the root so that `domain.*`, `ports.*` and the other packages resolve from any working directory.

A script holds that use case's UI and its steps, kept in separate functions; see [Inside an entry script](#3-inside-an-entry-script).

### Application

Orchestration: code that wires ports, domain and strategies into a task. It holds two kinds of module:

- **Steps shared by more than one use case.** `build_clean_dataset` (a folder of exports → one clean frame) is used by `rsi_divergence.py` and by `load_historical_data_use_case`.
- **One use case's steps, when they are big enough to need their own module and tests.** `load_backtest_config` is only used by `backtest.py`, but inlining its validation would make the script unreadable.

The question is "would the script stop being readable without this module?", not only "is it reused?". Modules are named `<task>_use_case.py`.

### Ports

Ports know *external resources*: file formats, config files, the clock, git. Anything read from or written to outside the process goes through a port.

- A port **parses records and stops**. No cleaning, no deduplication, no resampling, whether it hands back `Bar` objects or a DataFrame. That is the domain's job.
- Most ports are **stdlib-only** (no pandas, no numpy), so they run anywhere as-is. `mt5_file_access.mt5_frame_reader`, the histdata reader and the Dukascopy reader are the deliberate exceptions: they build a DataFrame directly. `backtest_result_access` imports no pandas but writes the result's DataFrames through their own methods.
- A port may import a domain **entity** it parses into or writes out, and the enums and name tables that spell it, never domain logic. The MT5 port parses files into `Bar` (`domain/bar_approach/bar.py`), but `Bar` belongs to the domain. `ports/backtest_result_access` writes a `BacktestResult` out, spelling its parameters with `timezone_name` and `SESSIONS`; what goes into the result (the split verdict included) is decided by the domain, how it looks on disk by the port.
- The clock and git are external resources too: `ports/run_environment/` provides `now()` and `git_commit()`. `backtest.py`'s `run_backtest` takes both as parameters, so tests pass fakes.

- A port may delegate the format itself to a [library](#libraries) and keep only what is specific to this application. `ports/dukascopy_file_access` takes each Dukascopy bid file and ask file from `libs.dukascopy_csv` and decides how they become one bar (OHLC from bid, spread from ask − bid). `ports/mt5_file_access` takes MetaTrader records and frames from `libs.metatrader_csv` and turns them into `Bar`s and the repo's frame shape (a blank volume is 0, a headerless 8-column export ends in the spread). `ports/histdata_file_access` reads histdata.com's downloads through the same library: same format, but its files name their own conventions (the always-zero volume is dropped, the clock is New York's, on the EU daylight-saving dates from 2019, only `DAT_MT_*.csv` files are sources).

Current ports: `mt5_file_access`, `histdata_file_access`, `dukascopy_file_access`, `file_system_access`, `backtest_config_access`, `backtest_result_access`, `run_environment`.

### Libraries

Code that knows a file format, or another external resource, and nothing about this application: no bars, no symbols, no backtests. Another project could copy a library's folder and use it unchanged.

- A library **imports nothing from the repo**, not even another library. Each one depends only on the standard library and third-party packages.
- **Only ports import libraries.** The port is where the library's general output is turned into what this application needs.
- One subpackage per library, `libs/<name>/`, with relative imports inside it and a `README.md` describing its API.

Current libraries: `dukascopy_csv` (find, pair and read Dukascopy candle exports, one DataFrame per file) and `metatrader_csv` (read and write MetaTrader bar exports, as records or a DataFrame).

### Domain

The domain knows *what the data means*: what one OHLC candle is, how bars collapse into a coarser timeframe, which of two rows claiming the same timestamp wins, how a trade is simulated and scored.

- It **never reads or writes files, the clock or git**. That is why `Backtest.run()` is domain, while recording a run (with its git commit and timestamp) is not.
- Helpers that aren't entities belong here only when they are about trading or market-data concepts (`broker_clock`, `sample_size`, `time_window`, `symbol`). A generic helper lives beside the code that uses it. There is no `utils` module, and there shouldn't be one.

### Strategies

The strategy plugins: `TradingStrategy` subclasses (pure logic on top of the domain), plus the `STRATEGIES` registry in `strategies/__init__.py`, through which application code and scripts find them by name. A base class several strategies share stays here too, unregistered: `opening_range.OpeningRangeStrategy` holds the ORB strategies' range and windows. Adding a strategy touches only this folder, its tests and its help page; see [Writing a new strategy](backtest-framework/writing-a-strategy.md).

### UI

UI logic reused by more than one entry script:

- table and report formatting: `text_table.format_table`, `frame_table_view.display_frame`;
- shared argparse argument types: `cli_args.timezone_arg`.

UI used by only one script stays in that script.

---

## 2. Import rules

These rules are the point of the layout. `tests/architecture/test_package_imports.py` enforces them, so breaking one fails `pytest`.

| Component | May import |
|---|---|
| entry scripts | `application`, `ports`, `domain`, `strategies`, `ui` |
| `application/` | `ports`, `domain`, `strategies` |
| `strategies/` | `domain` |
| `ports/` | the domain names listed in `PORT_DOMAIN_NAMES` (entities, and the enums and name tables that spell them), `libs` |
| `libs/` | nothing in the repo; each library only its own modules |
| `ui/` | `domain` (to format entities); never `ports` or `application` |
| `domain/` | nothing in the repo |

Also:

- **Nothing imports an entry script** (tests aside). Code two scripts need goes into a package.
- Every component may import its own modules, the standard library and third-party packages.
- The test reads imports with `ast`, so code examples in docstrings don't count. Imports inside functions and `TYPE_CHECKING` blocks do.

Keeping the test in step:

- A new domain name a port needs (an entity, an enum, a name table) → add it under its module in `PORT_DOMAIN_NAMES`. Names, not modules: a port may take `BacktestResult` from `domain.backtesting.backtest` without being allowed `Backtest`.
- A new top-level package → add it to `PACKAGES` and `ALLOWED_IMPORTS`.

---

## 3. Inside an entry script

A script keeps its UI and its use case in separate functions:

- **`main()`** parses the arguments, calls the use case, prints or writes its result, and sets the exit code.
- **The use-case function** takes plain values and returns a result. It never prints and never sees `argparse`. Progress goes through a callback (`progress=print`).

```python
def main() -> int:
    args = _parse_args()                                     # UI
    result = run_task(args.source, args.timeframe,
                      progress=print)                        # the use case
    print(format_result(result))                             # UI
    return 0


def run_task(source: Path, timeframe: SampleSize, *, progress=None) -> TaskResult:
    data = some_port.read(source)                            # ports
    return domain_function(data, timeframe)                  # domain
```

Examples in the repo: `backtest.py`'s `run_backtest()` and `calculate_daily_sessions.py`'s `collect_sessions()`.

The split has two benefits:

- **Testable.** A test imports the use case from the script and checks its result, without argparse or captured output (`tests/backtest/`).
- **Easy to promote.** When a second caller appears (another script, a notebook, a parameter sweep), the function moves to `application/` unchanged.

---

## 4. Where does new code go?

| The code… | Goes in |
|---|---|
| reads or writes a file, a config, the clock, git | a port: `ports/<resource>/` |
| …and knows a format any application could use, nothing of this one | a library, `libs/<name>/`, wrapped by a port |
| defines a market or trading concept, or calculates something from bars | `domain/`, in its concept's package: `market_data/`, `backtesting/` or `indicators/` |
| decides where a strategy enters | `strategies/`, registered in `STRATEGIES` |
| combines ports and domain into a task used by one script | that script's use-case function |
| …used by two or more scripts, or too big for the script | `application/<task>_use_case.py` |
| parses arguments, formats output, used by one script | that script |
| …used by two or more scripts | `ui/` |

Tests mirror this layout under `tests/` (see `CLAUDE.md`, "Testing").

---

## 5. Inside the domain

`domain/` is split by concept, one package per page of the blueprint's [domain](architecture/domain/README.md):

| Package | Holds | Blueprint page |
|---|---|---|
| `domain/market_data/` | timeframes (`SampleSize`), instruments (`Symbol`), clocks, `TimeWindow`, `TradingSession`, the bar frame's operations (`frames`, `shift_timezone`, `session_ohlc`) and `HistoricalData` | [market-data.md](architecture/domain/market-data.md) |
| `domain/backtesting/` | the `TradingStrategy` contract, `Position`s, cost models, the exit rules (`Backtest`), trade results, splits and statistics | [backtesting.md](architecture/domain/backtesting.md) |
| `domain/indicators/` | the RSI, divergence detection and the entries divergences give | [indicators.md](architecture/domain/indicators.md) |
| `domain/bar_approach/` | one `Bar` object per candle, and the legacy engine built on it | [market-data.md](architecture/domain/market-data.md#6-bar-and-barblock), §6 and §9 |

- **New work goes in its concept's package**, on DataFrames: pandas is much faster on the multi-hundred-thousand-bar datasets. A concept none of them covers gets a package of its own, and a blueprint page.
- **The packages build on each other in one direction:** `indicators/` → `backtesting/` → `market_data/` → `bar_approach/` (an arrow means "imports"). `indicators/` takes `Side` from `backtesting/`; `backtesting/` runs on `market_data/`'s `HistoricalData`; `market_data/`'s `TradingSessionInstance` holds `Bar`s.
- **pandas comes only with the modules that need it.** Every package's `__init__` imports nothing, so a stdlib port can import `domain.bar_approach.bar` or `domain.market_data.trading_session` without gaining a pandas dependency.
- **`bar_approach/` is stdlib only and stays only for the code and tests that still use it.** `bar.py` being stdlib-only is what lets the stdlib ports depend on it.
