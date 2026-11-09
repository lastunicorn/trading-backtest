# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A backtesting toolkit for intraday FX strategies (mostly EURUSD): readers for raw MT5, histdata.com and Dukascopy M1 data, a backtest framework that runs every strategy under the same simulation rules (see [Backtest framework](#backtest-framework)), and a few command-line utilities for inspecting and resampling data. Entry scripts sit at the repo root; everything else is a package they import.

## Reviewing requests

Before implementing a request as literally stated, check it against good practice, and say so if a better approach exists rather than silently building the literal ask. "Good" means:

- Easy for a human to read, easy to maintain long-term, easy to debug and extend.
- Leaves a seam where a future need is genuinely likely — a parameter, a hook, a clear boundary — without building the extension itself. A small amount of extra effort here is worth it; building the unrequested feature is not.

## Environment

Use `python3`, not `python` — this machine has only `/usr/bin/python3` (3.14), so bare `python` fails with `command not found`. Inside an activated venv both names work.

Requires only `pandas` + `numpy`, installed in the repo-local venv at `.venv/` (gitignored). **Activate it before running anything:**

```bash
source .venv/bin/activate      # prompt gains (.venv); `python` and `python3` both work
```

Pinned versions live in `requirements.txt` (currently pandas 3.0.5, numpy 2.5.2 on Python 3.14.4); `requirements-dev.txt` includes it and adds `pytest`. To rebuild the environment from scratch:

```bash
sudo apt install python3-venv       # one-time; the system Python is PEP 668 "externally managed"
rm -rf .venv
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
```

A venv hard-codes its absolute path (in `pyvenv.cfg` and every `bin/` script's shebang), so **moving or renaming the repo folder breaks `.venv/`**: rebuild it as above rather than patching it.

Raw data lives under `data/` (gitignored, local-only); `data/eurusd/1min/EURUSD_YYYY_MM.csv` are this repo's monthly MT5 M1 broker exports.

## Code layout

**The architecture is documented in [doc/architecture.md](doc/architecture.md). Read it before adding a module or moving code between folders, and keep it in sync when the structure changes.** In short: seven components, namely the entry scripts at the repo root (one per use case, with `main()` kept apart from the use-case function), `application/` (orchestration), `ports/` (external resources: files, config, clock, git), `libs/` (application-neutral file-format libraries that import nothing from the repo; only ports use them), `domain/` (concepts and calculations, no I/O), `strategies/` (the `TradingStrategy` plugins and the `STRATEGIES` registry) and `ui/` (UI shared by scripts). Their import rules are enforced by `tests/architecture/test_package_imports.py`. **New domain work goes in `domain/pandas_approach/`**, not `bar_approach/`.

The modules, one line each:

```
ports/mt5_file_access/mt5_bar_reader.py   MT5 CSV → `Bar` objects (dt, OHLC, volumes, spread), read only, via libs.metatrader_csv records [stdlib]
ports/mt5_file_access/mt5_frame_reader.py MT5 CSV ↔ the repo's bar frame, same fields, via libs.metatrader_csv frames [pandas]
ports/mt5_file_access/export_conventions.py  this repo's reading of the format: a headerless 8-column export ends in the spread
ports/histdata_file_access/histdata_frame_reader.py  histdata.com MT downloads → bar frame (OHLC only: the always-0 volume dropped), `FILE_PATTERN` `DAT_MT_*.csv`, `TIMEZONE` "histdata" [pandas]
ports/file_system_access/file_system.py   list the source csv files in a folder (or pass one file through) [stdlib]
ports/backtest_config_access/backtest_config_reader.py  backtest.py's JSON config → `BacktestConfig` (`StrategyConfig`, `DataSourceConfig`, `SimulationConfig` → `CostConfig`) (`read_config`): shape only — keys, JSON types, relative paths [stdlib]
ports/run_environment/run_environment.py  the wall clock (`now`) and the repo's git state (`git_commit` → `GitCommit(commit, dirty)`), for `run.json` [stdlib]
ports/dukascopy_file_access/dukascopy_frame_reader.py  Dukascopy bid/ask M1 pairs → one bar frame (OHLC from bid, spread = ask - bid): `read_path(folder or one file of a pair)` [pandas]
libs/metatrader_csv/                      read/write MetaTrader bar exports: `iterate_records`/`read_records`/`write_records` (stdlib) and `read_frame`/`write_frame` (pandas), `sniff_layout`; blank volumes stay None/NA; nothing from the repo, see its README.md
libs/dukascopy_csv/                       find (`find_files`), pair (`pair_files`, `find_pair`) and read (`read_file`) Dukascopy exports, one DataFrame per file, all columns kept; nothing from the repo, see its README.md [pandas]
domain/broker_clock.py                    BROKER_SERVER_TZ (New York + 7h), HISTDATA_TZ (New York; from 2019 London − 5h, a `SwitchingZone`), ShiftedZone, SwitchingZone, timezone_by_name ("broker", "histdata" or IANA) / timezone_name, is_utc [stdlib]
domain/time_window.py                     TimeWindow: daily [start, end) of timezone-aware times, each optional; ZonedTime annotation [stdlib]
domain/trading_session.py                 TradingSession: a session's daily window (zoned start/end, optional name); `create_session(date)`; SESSIONS table (TOKYO_SESSION, ASIA_SESSION, LONDON_SESSION, NEW_YORK_SESSION) [stdlib]
domain/trading_session_instance.py        TradingSessionInstance: one dated session window plus the `Bar`s inside it (a `BarBlock`: open/close/high/low) [stdlib]
domain/bar_approach/bar.py                the `Bar` entity — one OHLC candle (dt, OHLC, volumes, spread)  [stdlib]
domain/pandas_approach/frames.py          clean a frame (stable sort + dedup), resample it to a coarser timeframe, each bar labelled by its start (a week by its Monday) [pandas]
domain/pandas_approach/session_ohlc.py    session_ohlc(frame, session, timezone=): per-day open/high/low/close/bar_count of a TradingSession's window [pandas]
application/build_clean_dataset_use_case.py  folder of exports → one clean, deduplicated frame (in memory)
read_csv.py                               CLI that prints an export (`--source-format`: metatrader, histdata or dukascopy) as an aligned table, raw or resampled [pandas]
rsi_divergence.py                         CLI: RSI divergence indicator (regular, optionally hidden) on M5, printed; not the `RsiDivergence` entries [pandas]
calculate_daily_sessions.py               CLI: per-day open/high/low/close of SESSIONS entries (`--session`, default Asia) on the exports' `--source-timezone` (default broker), read by `load_source` for `--source-format` (a `SourceFormat`, default metatrader), via `session_ohlc`, printed [pandas]
show_symbols.py                           CLI: lists the `Symbol`s in domain.symbol with their pip/tick specs, `--filter` [stdlib]
```

```python
from ports.mt5_file_access import read_bars, iterate_bars   # short form (re-exported)

bars = read_bars(path)          # list[Bar] — fine for one monthly export (~31k bars)
for bar in iterate_bars(path):  # generator — constant memory; use on multi-million-row files
    ...
```

The format itself is `libs.metatrader_csv`: it detects the separator (comma/tab/semicolon), handles both headerless exports and `<DATE>`-style MT5 headers, and returns blank volumes as None/NA; the port fills them with 0 and builds `Bar`s or the repo's frame. `strict=True` (the default for every reader) raises `BarParseError` (an alias of `MetatraderParseError`) on a malformed line; `strict=False` skips it and reports it via an `on_skip(line_no, line, reason)` callback. Bars and frames skip the same lines and report them identically. `libs.metatrader_csv.sniff_layout(path)` reports which fields an export carries without parsing it.

Everything after parsing is `domain/` (concepts) and `application/` (use cases):

```python
from ports.mt5_file_access import read_frame
from domain.pandas_approach.frames import resample_ohlc
from application.build_clean_dataset_use_case import build_clean_dataset

m5 = resample_ohlc(read_frame("data/eurusd/1min/EURUSD_2020_01.csv"), "M5")

frame = build_clean_dataset("data/eurusd/1min", progress=print)  # every export in the folder, as one frame
```

`build_clean_dataset` takes the per-file reader (`read_file`, MT5 by default) and file `pattern` as parameters, which is how `load_histdata` reuses it. It merges every file's bars (dropping duplicate timestamps, the later file winning) *before* resampling, so a bar spanning two files — a week across a month boundary — gets both files' data. It returns the frame and never writes; what happened to each file (rows, skipped lines, errors) goes only to `progress`; a file that fails to parse is skipped, not fatal.

`read_csv.py`'s `source` is a single file or a folder of exports, read by `--source-format`'s port (`metatrader` by default, `histdata` or `dukascopy`; `read_source`). A metatrader/histdata folder is read file-by-file in name order (`ports.file_system_access.find_files`, `*.csv` / `DAT_MT_*.csv`), chronological for monthly exports. Every format comes out in the MT5 export shape with only the columns it has: Dukascopy's empty volumes are dropped and its ask − bid spread is converted to points with `--source-symbol`'s tick size, which is therefore required for it (and `--source-timezone` must be UTC). It runs a pandas pipeline: read every file into one frame, clean it up (stable sort + drop duplicate timestamps, `domain.pandas_approach.frames.clean_frame`), optionally shift timezone (`--timezone`, off by default, from the exports' clock `--source-timezone`, `broker` by default), optionally resample (`--timeframe`, via `domain.pandas_approach.frames.resample_ohlc` with plain pandas bucket semantics — see `domain.sample_size.SampleSize` for the `5m`/`4h`/`7d`/`2w`/`3M` syntax), then display or write (`--output`, which always writes the full processed frame regardless of `--rows`/`--all`/`--tail`). `--output` is also how to export a resampled or time-shifted CSV: it writes the MT5 export shape, which `load_mt5` reads back, whatever the source format. Unlike `build_clean_dataset`, one unreadable file aborts the run:

```bash
python3 read_csv.py data/eurusd/1min/EURUSD_2020_01.csv   # first 20 bars (the source arg is required)
python3 read_csv.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
python3 read_csv.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
python3 read_csv.py path/to/export.csv --decimals 3
python3 read_csv.py data/eurusd/1min --timeframe 5m                 # whole folder, resampled to M5
python3 read_csv.py data/eurusd/1min --timezone UTC                # broker-server time -> UTC
python3 read_csv.py path/to/histdata --source-format histdata --source-timezone histdata --timezone UTC
python3 read_csv.py path/to/dukascopy --source-format dukascopy --source-timezone UTC --source-symbol EURUSD
python3 read_csv.py data/eurusd/1min --timeframe 5m --output scratch/jan_m5.csv  # write instead of display
```

`ports/`, `domain/` and `libs/` (and their subpackages), `application/` and `strategies/` are regular packages (each has an `__init__.py`), and the CLIs must stay at the repo root for `ports.*` / `domain.*` / `application.*` / `strategies.*` to resolve from any working directory.

## Backtest framework

A reusable way to backtest any strategy on the same bars and under the same rules, instead of each script re-implementing SL/TP resolution, costs and statistics. **User documentation is in `doc/backtest-framework/`: `README.md` (how the framework works, the simulation rules, the checklist) links to `running-a-backtest.md` (the CLI, the Python API, data sources), `backtest-config.md` (the JSON config: structure, every key, validation), `reading-the-backtest-results.md` (output files, every statistic and column), `writing-a-strategy.md` and `api-reference.md`. Keep them in sync when the framework's public API or CLI changes.** Each strategy has a folder `doc/strategies/<name>/`, indexed by `doc/strategies/README.md`: `<name>-implementation.md` (what the code does: rules, parameters, how to backtest it) and, when the strategy was written down before it was coded, `<name>-rules.md` (that original description). Add a folder with every new strategy. The requirements are in `doc/backtest-framework.md`. Everything is pandas (`domain/pandas_approach/`).

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
domain/pandas_approach/position.py         Position, PositionOutcome, EntryFill (at-level/at-open: where SL/TP checking starts), positions_to_frame
domain/pandas_approach/trading_strategy.py TradingStrategy base class (generate_positions, parameters, split_days)
domain/pandas_approach/cost_model.py       CostModel, FixedCost (default 1.7 pips), SpreadCost
domain/pandas_approach/trade_results.py    per-trade gross/cost/net pips, risk pips, net R, duration
domain/pandas_approach/splits.py           SplitMode (none/dvt/monthly/yearly), split_labels, Split, split_dates (the 60/20/20 cut), assign_splits
domain/pandas_approach/statistics.py       compute_statistics, statistics_by_split, max_drawdown, max_consecutive_losses
domain/pandas_approach/backtest.py         Backtest(strategy, data, cost_model, ambiguity_policy, splits).run(); exits (`_simulate`), AmbiguityPolicy
application/load_historical_data_use_case.py  load_mt5 / load_histdata / load_dukascopy / load_source(source, SourceFormat) → HistoricalData
strategies/__init__.py                     STRATEGIES registry: the names a backtest.py config's `strategy.name` accepts
strategies/narrow_asia_fade.py             Candle DNA — Narrow Asia London Fade (NarrowAsiaFade)
strategies/opening_range.py                OpeningRangeStrategy, the ORB strategies' base (not registered): a `TradingSession`'s (`session`, default New York) opening range, order window, time stop, `split_days`
strategies/orb_break_entry.py              Opening Range Break, break entry (OrbBreakEntry), the rules of doc/strategies/orb-break-entry/orb-break-entry-rules.md on an OpeningRangeStrategy
strategies/rsi_divergence.py               RSI divergence reversal (RsiDivergence), entries = the removed M15 scan `rsi_divergence_strategy.py`'s
strategies/session_breakout.py             Tokyo/Asian session breakout (SessionBreakout), the rules of the removed `session_breakout_strategy.py`
application/load_backtest_config_use_case.py  load_backtest_config: read_config + value checks (strategy, symbol, zone, timeframes) + strategy.parameters → field types; cost_model(CostConfig)
backtest.py                                the CLI (one arg: a JSON config, loaded by load_backtest_config → BacktestConfig), plus run_backtest → BacktestRun; build_run_info, format_report, write_results
backtests/<name>/backtest.json             ready-made configs: narrow_asia_fade, orb_break_entry (Dukascopy M1, spread), rsi_divergence_15m, rsi_divergence_dukascopy, session_breakout (script parity)
```

```bash
python3 backtest.py backtests/narrow_asia_fade            # a folder means its backtest.json

python3 backtest.py backtests/rsi_divergence_15m/backtest.json
python3 backtest.py backtests/rsi_divergence_dukascopy
python3 backtest.py backtests/orb_break_entry
python3 backtest.py backtests/session_breakout        # script parity settings
```

The only CLI argument is a JSON config (or a folder holding `backtest.json`); its keys are grouped by what they control. A required `strategy` object holds `name` (a `STRATEGIES` key, recorded as `run.json`'s `strategy.name` via `run_backtest(..., strategy_name=)`) and optional `parameters`. At the root: `out` and `splits` (`none` (default) | `dvt` | `monthly` | `yearly`, a `SplitMode`; it only groups the statistics, so it is not a simulation key). An optional `simulation` object holds the trading rules: `timeframe` (the bar size to backtest on, default `"5m"`), `ambiguity` and a `cost` object (`spread` — charge the bar's spread, `SpreadCost` — and `commission_pips` — flat pips per trade, the whole cost without `spread`; **no `simulation.cost` means zero cost**, not the domain's 1.7 default, so `narrow_asia_fade` sets `"commission_pips": 1.7`). A required `data_source` object describing the bars on disk (required `path` — a file or a folder —, `format` — `metatrader` | `histdata` | `dukascopy`, a `SourceFormat`, which picks the loader — and `symbol`, optional `timezone` — the clock of the source's timestamps, `"broker"` or an IANA name, default `"UTC"`, never inferred from the format —, and `timeframe` — the source's bar size, default `"1m"`, which `simulation.timeframe` must be a whole multiple of, checked by `SampleSize.can_be_resampled_from`). `strategy.parameters` is an object overriding the strategy's dataclass fields, type-checked against them (time fields as `"HH:MM"`, `ZonedTime` fields as `"HH:MM <zone>"`, `TradingSession` fields as a `SESSIONS` name such as `"London"`, `X | None` fields also `null`) and validated by building the strategy while the config loads. **Relative `data_source.path`/`out` paths resolve against the config file's folder, not the cwd.** Unknown keys and wrong types are errors, not ignored. `out` is required and is overwritten. It writes `positions.csv` (one row per trade), `statistics.txt` (the human report — read it first), `statistics.csv` (one row per split, for diffing runs) and `run.json` (strategy + parameters, data range, simulation settings, split mode, git commit, source).

**The rules every backtest runs under** (the defaults hold unless the config changes them):

- **Strategies decide entries only.** `generate_positions` returns *open* positions. It must not look past each signal's bar: it sees the whole history, so avoiding look-ahead is the strategy's job.
- **Hits** are checked on bid OHLC and fill at the level itself, even when a bar gaps through it (optimistic for SL). A bar touching both SL and TP is ambiguous: `simulation.ambiguity` `"exclude"` (the default) records it as `ambiguous` with no P&L; `assume-sl` (`NarrowAsiaFade`'s design) or `assume-tp` settle it.
- **Where SL/TP checking starts is each `Position`'s `entry_fill`**, set by the strategy, not a config key: `EntryFill.AT_LEVEL` (the default) skips the entry bar, which is right for entries at a level *inside* the bar; `AT_OPEN` checks it too, right for entries at a bar's *open* (the RSI strategy).
- **`exit_dt` is the moment the position must be flat.** Bars opening before it are traded; with no hit, it closes `manual-close` at the last such bar's close, with `close_dt = exit_dt`. `NarrowAsiaFade` trades its 14:00 bar, so it sets `exit_dt` to 14:05. When the bars run out first, the outcome is `end-of-data`.
- **Costs are subtracted before any statistic.** A win is `net_pips > 0`, which is not the same as `take-profit-hit`. `SpreadCost` charges a long the spread of its entry bar and a short the spread of its exit bar (the moment each one trades at the ask); a bar with no spread value (Dukascopy's days without ask prices) is charged 0, and the report ends with a Notes line listing those trades (`CostModel.notes` → `BacktestResult.notes`, also in `run.json`).
- **Statistics are reported for all trades, and per split when `splits` asks** (`SplitMode`, default `none`): `dvt` gives discovery/validation/test and ends the report with "Net positive in every split: yes/no"; `monthly`/`yearly` give one row per calendar period (a transposed table of key metrics; `statistics.csv` keeps all of them) and end with "Net positive in K of N months with trades". A trade belongs to the split of the day it opens. The days split over come from `TradingStrategy.split_days` (default: every day with a bar; `NarrowAsiaFade`: the weekdays with a usable Asia range). The `backtests/*/backtest.json` configs set `"splits": "dvt"`, except `rsi_divergence_15m` (`"yearly"`).

**Data clock and units.** `HistoricalData.data` has a naive `datetime` column that must be strictly increasing, plus float OHLC. Optional columns are Int64 `tick_volume`/`volume` and float `spread` **in pips**. `HistoricalData(...)` only validates; `HistoricalData.from_frame(...)` normalises first. Sources disagree; the loaders settle the spread unit, and the caller states the clock (every loader takes a required `timezone`, which labels the bars and shifts nothing):

| Source | Loader | Spread unit converted from | Clock (`data_source.timezone`) |
|---|---|---|---|
| this repo's MT5 broker exports, `read_csv.py --output` files (whatever their source) | `load_mt5` (via `build_clean_dataset`) | points (tick size) | `broker` |
| histdata.com MT exports (`DAT_MT_EURUSD_M1_*`) | `load_histdata` (volume dropped) | — (no spread column) | `histdata` (not checked) |
| Dukascopy bid/ask pairs | `load_dukascopy` (volume columns dropped) | price (ask − bid) | `UTC` (enforced) |

A strategy with wall-clock session windows (`NarrowAsiaFade`) raises on data that isn't on the broker-server clock (`BROKER_SERVER_TZ`), rather than trading the wrong hours.

**Adding a strategy:** subclass `TradingStrategy` as a frozen dataclass. Its fields become `parameters()`, land in `run.json`, and are what a config's `strategy.parameters` can set. Implement `generate_positions` (and `split_days` if it trades a subset of days), and register it in `strategies/STRATEGIES` to make it runnable from `backtest.py`. Put tests in `tests/strategies/<module>/`.

`SessionBreakout` reproduces `session_breakout_strategy.py`, a standalone backtest script it replaced, trade for trade (entry time, side, levels, outcome, close time and price). The script is deleted; `tests/strategies/session_breakout/test_script_parity.py` checks the port against the trades the script produced on a synthetic M1 random walk across a DST switch, recorded in `_script_trades.py` (never regenerate it from the port). On the 2020–2026 broker M5 data they agreed on all 912 trades. Parity settings: `strategy.parameters` `check_trigger_bar` true (its level entries marked `AT_OPEN`, as the script checked SL/TP on the trigger bar), `simulation` `ambiguity` `exclude`, `cost.commission_pips` 0. The port keeps the script's quirks, which are listed in `doc/strategies/session-breakout/session-breakout-implementation.md`.

## Testing

Unit tests live under `tests/`, mirroring the source package layout (`tests/domain/...`, `tests/application/...`, `tests/strategies/...`). `pytest.ini` sets `testpaths = tests`; run everything with `pytest` from the repo root (inside the activated venv). Shared builders for a test directory go in a `_fakes.py` module inside it. A test that needs local-only data must `skipif` the file is absent rather than fail.

For a class or module under test, create a directory named after the file being tested, and inside it one test file per function/method tested (e.g. `domain/trading_session.py`'s `TradingSession.start_time_on` is tested in `tests/domain/trading_session/test_start_time_on.py`). This holds even for small, single-line delegating methods — keep each function's tests isolated rather than folding several into one file. Give every package directory (including `tests/` itself and each subpackage) an `__init__.py`.

`tests/architecture/` checks the [import rules](doc/architecture.md#2-import-rules) across the whole repo rather than testing one module; it parses imports with `ast`, so examples in docstrings don't count.

## Methodology

- **Chronological 60/20/20 split** into discovery / validation / test (`"splits": "dvt"`, `split_dates()`). Never shuffle; dates are sorted and sliced.
- **Thresholds are fit on discovery days only, then frozen** for validation and test (e.g. `NarrowAsiaFade`'s `narrow_threshold_pips` = 21.72, the discovery Q1 of the Asia range).
- A result only counts when it holds in all three splits. Single-split results are noise.
- Costs are subtracted from every trade before any statistic; `NarrowAsiaFade` uses 1.7 pips round-trip.

## Gotchas

- `.gitignore` covers `/data/`, `/output/`, `/*_output/`, `/backtests/`, `.venv/` and `__pycache__/`: the raw exports, every run directory, the ready-made configs (and their `output/`) and the venv are all local-only.
- **The broker-server clock is New York + 7h**: GMT+2 in winter, GMT+3 in summer, switching on the **US** daylight-saving dates. FX opens Sunday 17:00 New York, which is Monday 00:00 on the server, so every week in the exports runs Monday 00:00 → Friday 23:55 with no weekend bars. It is also true in all 24 weeks of 2020–2026 where US and EU switch dates disagree, which rules out `Europe/Athens`. No IANA zone matches, so `domain.broker_clock.BROKER_SERVER_TZ` is a `ShiftedZone` (a real zone's wall clock plus a fixed shift). CLI timezone flags accept `broker` for it (`timezone_by_name`). pandas rejects custom `tzinfo`s, so `shift_timezone` converts through the base zone; never hand `BROKER_SERVER_TZ` to `tz_localize` directly. **Before 2026-09-28 the repo treated the server clock as plain `America/New_York`**, so any server→UTC conversion made before then is 7 hours off. That covers the `--timezone` output of `show_csv`/`read_csv_as_*`, `rsi_divergence_strategy.py`'s printed times (it shifted to UTC by default) and the removed `session_breakout_strategy.py`'s session windows. Anything that worked in server-clock hours directly (`NarrowAsiaFade`) was never affected.
- **histdata.com MT exports (`…/histdata/mt/<year>/DAT_MT_EURUSD_M1_*.csv`) are on New York's clock, switching daylight saving on the EU dates from 2019, not the broker clock** (`domain.broker_clock.HISTDATA_TZ`, config/CLI name `histdata`: plain `America/New_York` before 2019-01-01, London − 5h from then on). Most weeks that is New York time: the week opens Sunday 17:00 and the closes match the broker exports at +7h. In the ~4 weeks a year when the US and EU switch dates disagree (2026: Mar 8–29 and Oct 25–Nov 1) it stays UTC−5 while New York is UTC−4: the week opens Sunday 16:00 and the closes match at +8h. Checked against the broker closes for 2020–2025: all 315 weeks line up at the shift `histdata` predicts. The 2016–2018 downloads are plain New York time instead: their mismatch weeks open Sunday 17:00 and close Friday 16:59, which only New York's dates explain; the change happened between Nov 2018 and Mar 2019 (no mismatch week in between), so `HISTDATA_TZ` switches at 2019-01-01. There is no price reference before 2020, so 2016–2019 rest on week edges alone. histdata's 2023 is patchy: ~12 weeks open 1–2h late and close 1–3h early (~30% of bars missing), with prices still aligned. **Before 2026-11-04 the repo treated histdata as plain `America/New_York`**, so every histdata run before then had those weeks one hour off. Before 2026-09-29 `load_mt5` labelled every MT export as broker-server time, so any `backtests/` run on histdata before then (`narrow_asia_fade`'s stored `output/`) had its windows 7 hours off. Clock-agnostic strategies (`rsi_divergence`) are unaffected. Use `"format": "histdata"` with `"timezone": "histdata"` for histdata in a backtest config; the loader accepts any clock (it no longer checks), so the config must get it right. (`"metatrader"` still reads the files, unchecked, with an all-zero `tick_volume`.)
- Loading bars at a timeframe **finer** than the source silently relabels them: `load_mt5(M5 file, SampleSize.Parse("1m"), ...)` returns the M5 bars labelled 1m. Resampling only ever coarsens.
- `domain/bar_approach/`'s `DailySessionBase`, `DailyStrategyBase`, `position.py` (`PendingPosition`, `Outcome`) and `shift_bars` were `session_breakout_strategy.py`'s engine. The script is deleted and nothing uses them now, but they are kept on purpose: don't remove them as dead code.
- `RsiDivergence` reproduces the entries of `rsi_divergence_strategy.py`, an M15 scan removed in `55eda77`; backtest it with `"simulation": {"timeframe": "15m"}`. The root `rsi_divergence.py` is a different script: the plain indicator on **M5**, with no 30/70 band filter, so its divergences are not the strategy's entries.
