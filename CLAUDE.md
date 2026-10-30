# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A backtesting toolkit for intraday FX strategies (mostly EURUSD): readers for raw MT5, histdata.com and Dukascopy M1 data, a backtest framework that runs every strategy under the same simulation rules (see [Backtest framework](#backtest-framework)), and a few command-line utilities for inspecting and resampling data. Entry scripts sit at the repo root; everything else is a package they import.

## Reviewing requests

Before implementing a request as literally stated, check it against good practice, and say so if a better approach exists rather than silently building the literal ask. "Good" means:

- Easy for a human to read, easy to maintain long-term, easy to debug and extend.
- Leaves a seam where a future need is genuinely likely — a parameter, a hook, a clear boundary — without building the extension itself. A small amount of extra effort here is worth it; building the unrequested feature is not.

## Environment

Use `python3`, not `python` — this machine has only `/usr/bin/python3` (3.12), so bare `python` fails with `command not found`. Inside an activated venv both names work.

Requires only `pandas` + `numpy`, installed in the repo-local venv at `.venv/` (gitignored). **Activate it before running anything:**

```bash
source .venv/bin/activate      # prompt gains (.venv); `python` and `python3` both work
```

Pinned versions live in `requirements.txt` (currently pandas 3.0.5, numpy 2.5.2 on Python 3.12.3). To rebuild the environment from scratch:

```bash
sudo apt install python3.12-venv    # one-time; the system Python is PEP 668 "externally managed"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Raw data lives under `data/` (gitignored, local-only); `data/eurusd/1min/EURUSD_YYYY_MM.csv` are this repo's monthly MT5 M1 broker exports.

## Code layout

The application has six components. Five are packages (`application/`, `ports/`, `domain/`, `strategies/`, `ui/`); the sixth is the entry scripts at the repo root: `backtest.py`, `resample_csv.py`, `read_csv_as_frame.py`, `read_csv_as_bars.py`, `rsi_divergence.py`, `session_breakout_strategy.py`, `trading_sessions.py` and `show_symbol.py`.

- **Entry scripts** — one per use case, at the repo root. A script holds that use case's UI and its steps, kept apart in two kinds of function:
  - `main()` parses the arguments, calls the use case, prints or writes its result and sets the exit code;
  - the use-case function (`backtest.py`'s `run_backtest()`, `resample_csv.py`'s `resample()`) takes plain values and returns a result. It never prints and never sees `argparse`; progress goes through a callback (`progress=print`).

  That split is what lets a test import the use case from the script (`tests/backtest/`), and what makes promoting it to `application/` a move rather than a rewrite.
- **`application/`** — orchestration: code that wires `ports/` and `domain/` (and `strategies/`) into a task. It holds (a) steps shared by more than one use case (`build_clean_dataset`, used by `rsi_divergence.py` and `load_historical_data`), and (b) one use case's steps when they are big enough to deserve their own module and tests (`load_backtest_config`, only used by `backtest.py`). The test is "would the script stop being readable without this?", not only "is it reused?". Modules are named `<task>_use_case.py`.
- **`ports/`** knows *external resources*: file formats, config files — anything read from or written to outside the process. A port parses records and stops — no cleaning, no deduplication, no resampling, whether it hands back `Bar` objects or a DataFrame. Most ports are **stdlib-only** (no pandas, no numpy), so they run in any sandbox as-is; `mt5_file_access.mt5_frame_reader` is the deliberate exception, using pandas to build the DataFrame directly. A port may import a domain **entity** it parses into (`Bar`, in `domain/bar_approach/bar.py` — the MT5 port parses files into it but does not own it), never domain logic. The clock and git are external resources too; `backtest.py`'s `build_run_info` still reads them directly (a `ports/run_environment/` with `git_commit()` and `now()` is the intended home).
- **`domain/`** knows *what the data means*: what one OHLC candle is (`bar_approach.bar.Bar`), how bars collapse into a coarser timeframe (`pandas_approach.frames.resample_ohlc`), which of two rows claiming the same timestamp wins, and how a trade is simulated and scored. Non-entity helpers belong here only when they are about trading or market-data concepts (`broker_clock`, `sample_size`, `time_window`); a generic helper lives beside its user — never add a `utils` module. `domain/` never reads or writes files or the clock, which is why `Backtest.run()` is domain but recording a run is not.
- **`strategies/`** — the strategy plugins: `TradingStrategy` subclasses, pure logic on top of `domain/`, plus the `STRATEGIES` registry in `strategies/__init__.py` through which `application/` and the scripts find them. Adding a strategy touches only this folder (and its tests and help page).
- **`ui/`** — UI logic reused by more than one entry script: table and report formatting (`bar_window_view.format_table`, `frame_table_view.display_frame`), display windows (`bar_window.BarWindow`), and in future shared argument types and error → exit-code handling. UI used by one script stays in that script.

`domain/` holds two parallel approaches: `domain/bar_approach/` (one `Bar` object per candle, stdlib) and `domain/pandas_approach/` (DataFrames). **New work goes in `pandas_approach/`** — it is much faster on the multi-hundred-thousand-bar datasets; `bar_approach/` stays only for the scripts and tests that still use it. `domain/pandas_approach/` is where pandas lives; `domain/bar_approach/bar.py` is stdlib-only, which is what lets the stdlib ports depend on it.

**Import rules** — the point of the layout. `tests/architecture/test_package_imports.py` enforces them, so a violation fails `pytest`:

| Component | May import |
|---|---|
| entry scripts | `application`, `ports`, `domain`, `strategies`, `ui` |
| `application/` | `ports`, `domain`, `strategies` |
| `strategies/` | `domain` |
| `ports/` | domain **entities only** (`PORT_DOMAIN_ENTITIES` in the test; today just `domain.bar_approach.bar`) |
| `ui/` | `domain` (to format entities) — never `ports` or `application` |
| `domain/` | nothing in the repo |

Nothing imports an entry script (tests aside); code two scripts need goes in a package. Every component may import its own modules, the stdlib and third-party packages. A new domain entity a port needs goes into `PORT_DOMAIN_ENTITIES`; a new top-level package goes into the test's `PACKAGES` and `ALLOWED_IMPORTS`.

```
ports/mt5_file_access/mt5_bar_reader.py   MT5 CSV → `Bar` objects (dt, OHLC, volumes, spread)            [stdlib]
ports/mt5_file_access/mt5_frame_reader.py MT5 CSV → pandas frame directly, same fields                  [pandas]
ports/file_system_access/file_system.py   list the source csv files in a folder (or pass one file through) [stdlib]
ports/backtest_config_access/backtest_config_reader.py  backtest.py's JSON config → `BacktestConfig` (`read_config`): shape only — keys, JSON types, relative paths [stdlib]
ports/ducascopy/ducascopy_frame_reader.py Dukascopy bid/ask M1 pairs → pandas frame (OHLC from bid, spread = ask - bid); `read_frame(year)` from config.DATA_DIR, `read_path(folder or file)` [pandas]
domain/broker_clock.py                    BROKER_SERVER_TZ (New York + 7h), ShiftedZone, timezone_by_name ("broker" or IANA) / timezone_name [stdlib]
domain/time_window.py                     TimeWindow: daily [start, end) of timezone-aware times, each optional; ZonedTime annotation [stdlib]
domain/bar_approach/bar.py                the `Bar` entity — one OHLC candle (dt, OHLC, volumes, spread)  [stdlib]
domain/bar_approach/resample_bars.py      resample an iterable of `Bar` to a coarser grid, streaming    [stdlib]
domain/pandas_approach/frames.py          clean a frame (stable sort + dedup), resample it to a coarser timeframe [pandas]
application/build_clean_dataset_use_case.py  folder of exports → one clean, deduplicated frame (in memory)
read_csv_as_frame.py                      CLI that prints an export as an aligned table, raw or resampled [pandas]
read_csv_as_bars.py                       the same CLI built on `Bar` streams instead of a frame          [stdlib]
resample_csv.py                           folder/file of M1 exports → merged CSV on a coarser grid + report
```

```python
from ports.mt5_file_access import read_bars, iterate_bars   # short form (re-exported)

bars = read_bars(path)          # list[Bar] — fine for one monthly export (~31k bars)
for bar in iterate_bars(path):  # generator — constant memory; use on multi-million-row files
    ...
```

The reader detects the separator (comma/tab/semicolon) and handles both headerless exports and `<DATE>`-style MT5 headers. `strict=True` (default) raises `BarParseError` on a malformed line; `strict=False` skips it and reports via an `on_skip` callback. `detect_layout(path)` reports which fields an export carries without parsing it.

Everything after parsing is `domain/` (concepts) and `application/` (use cases):

```python
from ports.mt5_file_access import read_frame
from domain.pandas_approach.frames import resample_ohlc
from application.build_clean_dataset_use_case import build_clean_dataset

m5 = resample_ohlc(read_frame("data/eurusd/1min/EURUSD_2020_01.csv"), "M5")

frame = build_clean_dataset("data/eurusd/1min", progress=print)  # every export in the folder, as one frame
```

`build_clean_dataset` returns the frame and never writes; what happened to each file (rows, skipped lines, errors) goes only to `progress`.

`resample_csv.py` runs the same build as `build_clean_dataset()` through its own `resample()` function, and — unlike `build_clean_dataset` — does the writing itself. (`resample()` used to live in a separate `application/resample_use_case.py` module; since this script was its only caller, that logic now lives directly in `resample_csv.py`.) It emits two files: the resampled CSV (MT5 export shape, read back with `load_mt5`) and a report beside it named for the CSV (`output_M5.csv` → `output_M5.report.txt`), overwriting an existing file after printing an `INFO:` line. `--source`, `--destination` and `--timeframe` are all required (no defaults). `--source` is a folder of raw M1 exports or a single csv file — the source data must always be M1; `--destination` is a file path, or a directory, in which case it writes `output_<timeframe>.csv` inside it:

```bash
python3 resample_csv.py --source data/eurusd/1min --destination data/eurusd/5min/EURUSD.csv --timeframe M5
python3 resample_csv.py --source data/eurusd/1min --destination data/eurusd/15min/EURUSD.csv --timeframe M15
python3 resample_csv.py --source data/eurusd/1min/EURUSD_2020_01.csv --destination scratch/jan.csv --timeframe M5
```

`read_csv_as_frame.py`'s `source` is a single file or a folder of exports (`ports.file_system_access.find_files` — a folder is read file-by-file in name order, chronological for this repo's monthly exports). It runs a pandas pipeline: read every file into one frame, clean it up (stable sort + drop duplicate timestamps, `domain.pandas_approach.frames.clean_frame`), optionally shift timezone (`--timezone`, off by default — bars display in raw broker-server time otherwise), optionally resample (`--interval`, via `domain.pandas_approach.frames.resample_ohlc` with plain pandas bucket semantics — see `domain.sample_size.SampleSize` for the `5m`/`4h`/`7d`/`2w`/`3M` syntax), then display or write (`--output`, which always writes the full processed frame regardless of `--rows`/`--all`/`--tail`):

```bash
python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv   # first 20 bars (the source arg is required)
python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
python3 read_csv_as_frame.py path/to/export.csv --decimals 3
python3 read_csv_as_frame.py data/eurusd/1min --interval 5m                 # whole folder, resampled to M5
python3 read_csv_as_frame.py data/eurusd/1min --timezone UTC                # broker-server time -> UTC
python3 read_csv_as_frame.py data/eurusd/1min --interval 5m --output scratch/jan_m5.csv  # write instead of display
```

`ports/` and `domain/` (and their subpackages), `application/` and `strategies/` are regular packages (each has an `__init__.py`), and the CLIs must stay at the repo root for `ports.*` / `domain.*` / `application.*` / `strategies.*` to resolve from any working directory.

## Backtest framework

A reusable way to backtest any strategy on the same bars and under the same rules, instead of each script re-implementing SL/TP resolution, costs and statistics. **User documentation is in `help/backtest-framework/`: `README.md` (how the framework works, the simulation rules, the checklist) links to `running-a-backtest.md` (the CLI, the Python API, data sources), `backtest-config.md` (the JSON config: structure, every key, validation), `reading-the-backtest-results.md` (output files, every statistic and column), `writing-a-strategy.md`, `api-reference.md`, and one `strategy-<name>.md` per strategy. Keep them in sync when the framework's public API or CLI changes.** The requirements are in `backtest-framework.md` and the design rationale is in `backtest-framework-plan.md`. Everything is pandas (`domain/pandas_approach/`).

```
HistoricalData ─► TradingStrategy.generate_positions() ─► open Positions (entry, SL, TP, optional exit_dt)
                                                            │
                         Backtest._simulate() ◄─────────────┘   the ONE place exits are decided
                                │
       positions_to_frame ─► CostModel.cost_pips ─► trade_results ─► assign_splits ─► statistics_by_split
       └─────────────────────── Backtest.run() → BacktestResult(trades, statistics) ───────────────────┘   [domain, no I/O]
                                │
       run_backtest(): run_info (git, clock) + statistics.txt + 4 files                               [backtest.py]
```

```
domain/pandas_approach/historical_data.py  HistoricalData (frame + SampleSize + Symbol + timezone), SpreadUnit, locate()
domain/pandas_approach/side.py             Side ("long"/"short")
domain/pandas_approach/position.py         Position, PositionOutcome, positions_to_frame
domain/pandas_approach/trading_strategy.py TradingStrategy base class (generate_positions, parameters, split_days)
domain/pandas_approach/cost_model.py       CostModel, FixedCost (default 1.7 pips), SpreadCost
domain/pandas_approach/trade_results.py    per-trade gross/cost/net pips, risk pips, net R, duration
domain/pandas_approach/splits.py           SplitMode (none/dvt/monthly/yearly), split_labels, Split, split_dates (the 60/20/20 cut), assign_splits
domain/pandas_approach/statistics.py       compute_statistics, statistics_by_split, max_drawdown, max_consecutive_losses
domain/pandas_approach/backtest.py         Backtest(strategy, data, cost_model, ambiguity_policy, position_resolve_delay, splits).run(); exits (`_simulate`), AmbiguityPolicy, PositionResolveDelay
application/load_historical_data_use_case.py  load_mt5 / load_dukascopy / load_source(source, SourceFormat) → HistoricalData
strategies/__init__.py                     STRATEGIES registry: the names a backtest.py config's `strategy` accepts
strategies/narrow_asia_fade.py             Candle DNA — Narrow Asia London Fade (NarrowAsiaFade)
strategies/rsi_divergence.py               RSI divergence reversal (RsiDivergence), entries = rsi_divergence_strategy.py's
strategies/session_breakout.py             Tokyo/Asian session breakout (SessionBreakout), session_breakout_strategy.py's rules
application/load_backtest_config_use_case.py  load_backtest_config: read_config + value checks (strategy, symbol, zone, timeframes) + strategy_parameters → field types; cost_model(CostConfig)
backtest.py                                the CLI (one arg: a JSON config, loaded by load_backtest_config → BacktestConfig), plus run_backtest → BacktestRun; build_run_info, format_report, write_results
backtests/<name>/backtest.json             ready-made configs: narrow_asia_fade, rsi_divergence, rsi_divergence_dukascopy, session_breakout (script parity)
```

```bash
python3 backtest.py backtests/narrow_asia_fade            # a folder means its backtest.json

python3 backtest.py backtests/rsi_divergence/backtest.json
python3 backtest.py backtests/rsi_divergence_dukascopy
python3 backtest.py backtests/session_breakout        # script parity settings
```

The only CLI argument is a JSON config (or a folder holding `backtest.json`); its keys are the old flags in snake_case (`strategy`, `out`, `timeframe`, `ambiguity`, `resolve_from`, `splits` — `none` (default) | `dvt` | `monthly` | `yearly`, a `SplitMode`), an optional `cost` object (`spread` — charge the bar's spread, `SpreadCost` — and `commission_pips` — flat pips per trade, the whole cost without `spread`; **no `cost` means zero cost**, not the domain's 1.7 default, so `narrow_asia_fade` sets `"commission_pips": 1.7`), a required `data` object describing the bars on disk (required `source`, `format` — `metatrader` | `dukascopy`, a `SourceFormat`, which picks the loader — and `symbol`, optional `timezone` — the clock of the source's timestamps, `"broker"` or an IANA name, default `"UTC"`, never inferred from the format —, and `timeframe` — the source's bar size, default `"1m"`, which the root `timeframe` must be a whole multiple of, checked by `SampleSize.can_be_resampled_from`), plus `strategy_parameters`: an object overriding the strategy's dataclass fields, type-checked against them (time fields as `"HH:MM"`, `ZonedTime` fields as `"HH:MM <zone>"`, `X | None` fields also `null`) and validated by building the strategy while the config loads. **Relative `data.source`/`out` paths resolve against the config file's folder, not the cwd.** Unknown keys and wrong types are errors, not ignored. `out` is required and is overwritten. It writes `positions.csv` (one row per trade), `statistics.txt` (the human report — read it first), `statistics.csv` (one row per split, for diffing runs) and `run.json` (strategy + parameters, data range, simulation settings, git commit, source).

**The rules every backtest runs under** (the defaults hold unless the config changes them):

- **Strategies decide entries only.** `generate_positions` returns *open* positions. It must not look past each signal's bar: it sees the whole history, so avoiding look-ahead is the strategy's job.
- **Hits** are checked on bid OHLC and fill at the level itself, even when a bar gaps through it (optimistic for SL). A bar touching both SL and TP is ambiguous: `"ambiguity": "exclude"` (the default) records it as `ambiguous` with no P&L; `assume-sl` (`NarrowAsiaFade`'s design) or `assume-tp` settle it.
- **`resolve_from`**: `next-bar` (the default) skips the entry bar, which is right for entries at a level *inside* the bar. `entry-bar` is right for entries at a bar's *open* (the RSI strategy).
- **`exit_dt` is the moment the position must be flat.** Bars opening before it are traded; with no hit, it closes `manual-close` at the last such bar's close, with `close_dt = exit_dt`. `NarrowAsiaFade` trades its 14:00 bar, so it sets `exit_dt` to 14:05. When the bars run out first, the outcome is `end-of-data`.
- **Costs are subtracted before any statistic.** A win is `net_pips > 0`, which is not the same as `take-profit-hit`. `SpreadCost` charges a long the spread of its entry bar and a short the spread of its exit bar (the moment each one trades at the ask).
- **Statistics are reported for all trades, and per split when `splits` asks** (`SplitMode`, default `none`): `dvt` gives discovery/validation/test and ends the report with "Net positive in every split: yes/no"; `monthly`/`yearly` give one row per calendar period (a transposed table of key metrics; `statistics.csv` keeps all of them) and end with "Net positive in K of N months with trades". A trade belongs to the split of the day it opens. The days split over come from `TradingStrategy.split_days` (default: every day with a bar; `NarrowAsiaFade`: the weekdays with a usable Asia range). The `backtests/*/backtest.json` configs set `"splits": "dvt"`.

**Data clock and units.** `HistoricalData.data` has a naive `datetime` column that must be strictly increasing, plus float OHLC. Optional columns are Int64 `tick_volume`/`volume` and float `spread` **in pips**. `HistoricalData(...)` only validates; `HistoricalData.from_frame(...)` normalises first. Sources disagree; the loaders settle the spread unit, and the caller states the clock (every loader takes a required `timezone`, which labels the bars and shifts nothing):

| Source | Loader | Spread unit converted from | Clock (`data.timezone`) |
|---|---|---|---|
| this repo's MT5 broker exports, `resample_csv.py` output | `load_mt5` (via `build_clean_dataset`) | points (tick size) | `broker` |
| histdata.com MT exports (`DAT_MT_EURUSD_M1_*`) | `load_mt5` | — (no spread column) | `America/New_York` |
| Dukascopy bid/ask pairs | `load_dukascopy` (volume columns dropped) | price (ask − bid) | `UTC` (enforced) |

A strategy with wall-clock session windows (`NarrowAsiaFade`) raises on data that isn't on the broker-server clock (`BROKER_SERVER_TZ`), rather than trading the wrong hours.

**Adding a strategy:** subclass `TradingStrategy` as a frozen dataclass. Its fields become `parameters()`, land in `run.json`, and are what a config's `strategy_parameters` can set. Implement `generate_positions` (and `split_days` if it trades a subset of days), and register it in `strategies/STRATEGIES` to make it runnable from `backtest.py`. Put tests in `tests/strategies/<module>/`.

`SessionBreakout` reproduces `session_breakout_strategy.py` trade for trade (entry time, side, levels, outcome, close time and price). `tests/strategies/session_breakout/test_script_parity.py` runs both on a synthetic M1 random walk across a DST switch. On the 2020–2026 broker M5 data they agreed on all 912 trades. Parity settings: `entry-bar`, `exclude`, `cost.commission_pips` 0. The port keeps the script's quirks, which are listed in `help/backtest-framework/strategy-session-breakout.md`.

## Testing

Unit tests live under `tests/`, mirroring the source package layout (`tests/domain/...`, `tests/application/...`, `tests/strategies/...`). `pytest.ini` sets `testpaths = tests`; run everything with `pytest` from the repo root (inside the activated venv). Shared builders for a test directory go in a `_fakes.py` module inside it. A test that needs local-only data must `skipif` the file is absent rather than fail.

For a class or module under test, create a directory named after the file being tested, and inside it one test file per function/method tested (e.g. `domain/trading_session_template.py`'s `TradingSessionTemplate.start_time_on` is tested in `tests/domain/trading_session_template/test_start_time_on.py`). This holds even for small, single-line delegating methods — keep each function's tests isolated rather than folding several into one file. Give every package directory (including `tests/` itself and each subpackage) an `__init__.py`.

`tests/architecture/` checks the [import rules](#code-layout) across the whole repo rather than testing one module; it parses imports with `ast`, so examples in docstrings don't count.

## Methodology

- **Chronological 60/20/20 split** into discovery / validation / test (`"splits": "dvt"`, `split_dates()`). Never shuffle; dates are sorted and sliced.
- **Thresholds are fit on discovery days only, then frozen** for validation and test (e.g. `NarrowAsiaFade`'s `narrow_threshold_pips` = 21.72, the discovery Q1 of the Asia range).
- A result only counts when it holds in all three splits. Single-split results are noise.
- Costs are subtracted from every trade before any statistic; `NarrowAsiaFade` uses 1.7 pips round-trip.

## Gotchas

- `.gitignore` covers `/data/`, `/output/`, `/*_output/`, `.venv/` and `__pycache__/`: the raw exports, every run directory, and the venv are all local-only.
- **The broker-server clock is New York + 7h**: GMT+2 in winter, GMT+3 in summer, switching on the **US** daylight-saving dates. FX opens Sunday 17:00 New York, which is Monday 00:00 on the server, so every week in the exports runs Monday 00:00 → Friday 23:55 with no weekend bars. It is also true in all 24 weeks of 2020–2026 where US and EU switch dates disagree, which rules out `Europe/Athens`. No IANA zone matches, so `domain.broker_clock.BROKER_SERVER_TZ` is a `ShiftedZone` (a real zone's wall clock plus a fixed shift). CLI timezone flags accept `broker` for it (`timezone_by_name`). pandas rejects custom `tzinfo`s, so `shift_timezone` converts through the base zone; never hand `BROKER_SERVER_TZ` to `tz_localize` directly. **Before 2026-09-28 the repo treated the server clock as plain `America/New_York`**, so any server→UTC conversion made before then is 7 hours off. That covers the `--timezone` output of `show_csv`/`read_csv_as_*`, `rsi_divergence_strategy.py`'s printed times (it shifted to UTC by default) and `session_breakout_strategy.py`'s session windows. Anything that worked in server-clock hours directly (`NarrowAsiaFade`) was never affected.
- **histdata.com MT exports (`…/histdata/mt/<year>/DAT_MT_EURUSD_M1_*.csv`) are on New York time, not the broker clock.** Their week opens Sunday 17:00 in both winter and summer, and their July 2025 closes match the broker exports at exactly +7h (median 0.5 pips apart, vs 5+ at +6h/+8h). Before 2026-09-29 `load_mt5` labelled every MT export as broker-server time, so any `backtests/` run on histdata before then (`narrow_asia_fade`'s stored `output/`) had its windows 7 hours off. Clock-agnostic strategies (`rsi_divergence`) are unaffected. Set `"timezone": "America/New_York"` for histdata in a backtest config.
- Loading bars at a timeframe **finer** than the source silently relabels them: `load_mt5(M5 file, SampleSize.Parse("1m"), ...)` returns the M5 bars labelled 1m. Resampling only ever coarsens.
- `rsi_divergence_strategy.py` (the scan) runs on **M15**, not M5 (`TIMEFRAME`); backtest `rsi_divergence` with `"timeframe": "15m"` to match it.
- `read_csv_as_frame.py --output` is **not** a substitute for `resample_csv.py`, even though both can write a resampled CSV. `resample_csv.py` resamples each source file individually and dedups the *resampled* rows across files afterward, matching `build_clean_dataset` and its month-boundary tie-break; it's also the only one of the two that writes a `.report.txt` provenance record and that survives a single bad source file (per-file errors are logged, not fatal). `read_csv_as_frame.py` concatenates every raw file first, dedups the *raw M1* rows once, then resamples the whole thing — a different tie-break at month boundaries, no report, and one bad file aborts the run. Use `resample_csv.py` for anything that feeds a backtest; `read_csv_as_frame.py` is for ad hoc inspection.
