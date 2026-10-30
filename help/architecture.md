# Architecture

How the code is split into components, what each one is responsible for, and which component may depend on which. Read this before adding a module or moving code between folders.

## Contents

1. [The components](#1-the-components)
2. [Import rules](#2-import-rules)
3. [Inside an entry script](#3-inside-an-entry-script)
4. [Where does new code go?](#4-where-does-new-code-go)
5. [Two domain approaches: bars and frames](#5-two-domain-approaches-bars-and-frames)

---

## 1. The components

The application has six components. Five are packages; the sixth is the set of entry scripts at the repo root.

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
   │ ports │   │                │                   │
   └───┬───┘   │                │                   │
       │ entities only          │                   │
       ▼       ▼                ▼                   ▼
   ┌───────────────────────────────────────────────────────┐
   │                         domain                        │
   └───────────────────────────────────────────────────────┘
```

*An arrow means "may import". Entry scripts may also import `ports` and `domain` directly (not drawn). Everything points towards `domain/`, which imports nothing in the repo.*

| Component | Where | Responsible for |
|---|---|---|
| **Entry scripts** | `*.py` at the repo root | one use case each: its UI and its steps |
| **Application** | `application/` | orchestration shared by use cases, or too big for one script |
| **Ports** | `ports/` | talking to external resources: files, config, the clock, git |
| **Domain** | `domain/` | the concepts and the calculations; no I/O |
| **Strategies** | `strategies/` | the `TradingStrategy` plugins and their registry |
| **UI** | `ui/` | UI logic reused by more than one entry script |

### Entry scripts

One script per use case, at the repo root: `backtest.py`, `resample_csv.py`, `read_csv_as_frame.py`, `read_csv_as_bars.py`, `rsi_divergence.py`, `session_breakout_strategy.py`, `trading_sessions.py`, `show_symbol.py`. They must stay at the root so that `domain.*`, `ports.*` and the other packages resolve from any working directory.

A script holds that use case's UI and its steps, kept in separate functions; see [Inside an entry script](#3-inside-an-entry-script).

### Application

Orchestration: code that wires ports, domain and strategies into a task. It holds two kinds of module:

- **Steps shared by more than one use case.** `build_clean_dataset` (a folder of exports → one clean frame) is used by `rsi_divergence.py` and by `load_historical_data_use_case`.
- **One use case's steps, when they are big enough to need their own module and tests.** `load_backtest_config` is only used by `backtest.py`, but inlining its validation would make the script unreadable.

The question is "would the script stop being readable without this module?", not only "is it reused?". Modules are named `<task>_use_case.py`.

### Ports

Ports know *external resources*: file formats, config files, the clock, git. Anything read from or written to outside the process goes through a port.

- A port **parses records and stops**. No cleaning, no deduplication, no resampling, whether it hands back `Bar` objects or a DataFrame. That is the domain's job.
- Most ports are **stdlib-only** (no pandas, no numpy), so they run anywhere as-is. `mt5_file_access.mt5_frame_reader` and the Dukascopy reader are the deliberate exceptions: they build a DataFrame directly.
- A port may import a domain **entity** it parses into, never domain logic. The MT5 port parses files into `Bar` (`domain/bar_approach/bar.py`), but `Bar` belongs to the domain.
- The clock and git are external resources too: `ports/run_environment/` provides `now()` and `git_commit()`. `backtest.py`'s `build_run_info` takes both as parameters, so tests pass fakes.

Current ports: `mt5_file_access`, `ducascopy`, `file_system_access`, `backtest_config_access`, `run_environment`.

### Domain

The domain knows *what the data means*: what one OHLC candle is, how bars collapse into a coarser timeframe, which of two rows claiming the same timestamp wins, how a trade is simulated and scored.

- It **never reads or writes files, the clock or git**. That is why `Backtest.run()` is domain, while recording a run (with its git commit and timestamp) is not.
- Helpers that aren't entities belong here only when they are about trading or market-data concepts (`broker_clock`, `sample_size`, `time_window`, `symbol`). A generic helper lives beside the code that uses it. There is no `utils` module, and there shouldn't be one.

### Strategies

The strategy plugins: `TradingStrategy` subclasses (pure logic on top of the domain), plus the `STRATEGIES` registry in `strategies/__init__.py`, through which application code and scripts find them by name. Adding a strategy touches only this folder, its tests and its help page; see [Writing a new strategy](backtest-framework/writing-a-strategy.md).

### UI

UI logic reused by more than one entry script:

- table and report formatting: `bar_window_view.format_table`, `frame_table_view.display_frame`;
- display windows: `bar_window.BarWindow`;
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
| `ports/` | domain **entities only**; today just `domain.bar_approach.bar` |
| `ui/` | `domain` (to format entities); never `ports` or `application` |
| `domain/` | nothing in the repo |

Also:

- **Nothing imports an entry script** (tests aside). Code two scripts need goes into a package.
- Every component may import its own modules, the standard library and third-party packages.
- The test reads imports with `ast`, so code examples in docstrings don't count. Imports inside functions and `TYPE_CHECKING` blocks do.

Keeping the test in step:

- A new domain entity a port needs → add it to `PORT_DOMAIN_ENTITIES`.
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

Examples in the repo: `backtest.py`'s `run_backtest()` and `resample_csv.py`'s `resample()`.

The split has two benefits:

- **Testable.** A test imports the use case from the script and checks its result, without argparse or captured output (`tests/backtest/`).
- **Easy to promote.** When a second caller appears (another script, a notebook, a parameter sweep), the function moves to `application/` unchanged.

---

## 4. Where does new code go?

| The code… | Goes in |
|---|---|
| reads or writes a file, a config, the clock, git | a port: `ports/<resource>/` |
| defines a market or trading concept, or calculates something from bars | `domain/` (`pandas_approach/` for frame code) |
| decides where a strategy enters | `strategies/`, registered in `STRATEGIES` |
| combines ports and domain into a task used by one script | that script's use-case function |
| …used by two or more scripts, or too big for the script | `application/<task>_use_case.py` |
| parses arguments, formats output, used by one script | that script |
| …used by two or more scripts | `ui/` |

Tests mirror this layout under `tests/` (see `CLAUDE.md`, "Testing").

---

## 5. Two domain approaches: bars and frames

`domain/` holds two parallel approaches:

- `domain/bar_approach/`: one `Bar` object per candle, stdlib only. `bar.py` being stdlib-only is what lets the stdlib ports depend on it.
- `domain/pandas_approach/`: DataFrames; this is where pandas lives.

**New work goes in `pandas_approach/`.** It is much faster on the multi-hundred-thousand-bar datasets. `bar_approach/` stays only for the scripts and tests that still use it.
