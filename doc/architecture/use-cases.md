# Use Cases

What the application does, as tasks that wire [ports](ports/README.md), the [domain](domain-backtest.md) and the [plugins](plugins/README.md) together. Each use case lists its input and output DTOs, its steps and the errors it can return. A use case never prints and never parses command-line arguments: it takes plain values, returns a result and reports progress through a callback ([conventions.md](conventions.md#4-progress-reporting)). The CLIs that call them are in [ui.md](ui.md).

In the Python code, a use case shared by several scripts (or too big for one) is a module in `application/`; the others are a function inside their entry script. Each section names where it lives.

## Contents

| # | Use case | Called by | Python |
|---|---|---|---|
| 1 | [BuildCleanDataset](#1-buildcleandataset) | LoadHistoricalData, ScanRsiDivergences | `application/build_clean_dataset_use_case.py` |
| 2 | [LoadHistoricalData](#2-loadhistoricaldata) | RunBacktestFromConfig, CollectDailySessions | `application/load_historical_data_use_case.py` |
| 3 | [LoadBacktestConfig](#3-loadbacktestconfig) | RunBacktestFromConfig | `application/load_backtest_config_use_case.py` |
| 4 | [RecordBacktest](#4-recordbacktest) | RunBacktestFromConfig, library callers | `backtest.py` (`run_backtest`) |
| 5 | [RunBacktestFromConfig](#5-runbacktestfromconfig) | `backtest` CLI | `backtest.py` (`_run`) |
| 6 | [PrepareBars](#6-preparebars) | `read_csv` CLI | `read_csv.py` (`read_source` and `main`) |
| 7 | [ScanRsiDivergences](#7-scanrsidivergences) | `rsi_divergence` CLI | `rsi_divergence.py` (`main`) |
| 8 | [CollectDailySessions](#8-collectdailysessions) | `calculate_daily_sessions` CLI | `calculate_daily_sessions.py` (`collect_sessions`) |
| 9 | [ListSymbols](#9-listsymbols) | `show_symbols` CLI | `show_symbols.py` |

### SourceFormat (Enum)

How a source's files are laid out, which picks the bar port. Shared by several use cases, the config's `data_source.format` and the CLIs' `--source-format`.

| Value | Wire | Files |
|---|---|---|
| `METATRADER` | `metatrader` | MetaTrader exports (`*.csv`): a folder of them, or one |
| `HISTDATA` | `histdata` | histdata.com downloads (`DAT_MT_*.csv`): a folder of them, or one |
| `DUKASCOPY` | `dukascopy` | Dukascopy bid/ask pairs: a folder of them (recursive), or one file of a pair |

---

## 1. BuildCleanDataset

A folder of exports (or one file) → one clean, resampled bar table, in memory. It merges every file's bars **before** resampling, so a bar spanning two files (a week across a month boundary) gets both files' data. One bad file never aborts the build.

### Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `input_path` | `Path` | | a folder or one file |
| `timeframe` | `SampleSize` | `5m` | the bar size to resample to |
| `skip_parts` | `List<String>` | `[]` | file-name fragments marking generated files to ignore |
| `pattern` | `String` | `*.csv` | which files in the folder are sources |
| `read_file` | a bar port's `read_frame` | MetatraderBarFiles' | called as `read_file(path, strict = false, on_skip)` |
| `progress` | callback? | `null` | |

### Output

`Table<BarRow>`: clean (sorted, no duplicate timestamps) and resampled to `timeframe`.

### Steps

1. `files = FileSystem.find_files(input_path, pattern, skip_parts)`. Progress: `Found {n} candidate source CSV files.`
2. For each file, in name order (`i` from 1):
   1. Progress: `[{i}/{n}] {file name}`.
   2. `read_file(path, strict = false, on_skip = count)`, counting the skipped lines.
   3. If reading fails with any error: progress `    ERROR: {message}`; skip the file.
   4. If the table is empty: progress `    SKIP: no usable rows`; skip the file.
   5. Otherwise progress `    OK: {rows} rows` (plus `, {k} unparsable lines skipped` when `k > 0`; numbers with thousands separators) and `        {first datetime} -> {last datetime}`; keep the table.
3. No table kept: `NO_USABLE_SOURCE_FILES`.
4. Progress `Combining the files...`. Concatenate the tables in file order, then `clean_frame` (so where two files hold the same timestamp, the later file wins). Progress `Removed {k} duplicate timestamps.`
5. Return `resample_ohlc(table, timeframe)`.

Peak memory is the whole source history (about 2.4 million rows for six years of M1).

### Errors

| Code | Description |
|---|---|
| `NO_USABLE_SOURCE_FILES` | No file produced any bar (none found, all unreadable or empty): `No usable source files. See errors above.` |

Per-file errors never escape; they are reported through `progress`.

---

## 2. LoadHistoricalData

Bars from any supported source → `HistoricalData`. This is where the sources' differences are settled: which port reads them, and which unit their spread is in. The clock is **not** a property of the format: the caller states it, and it labels the bars without shifting them.

### Input

| Field | Type | Notes |
|---|---|---|
| `source` | `Path` | a folder or one file |
| `source_format` | `SourceFormat` | |
| `timeframe` | `SampleSize` | the bar size wanted |
| `symbol` | `Symbol` | |
| `timezone` | `TimeZone` | the clock of the source's timestamps |
| `progress` | callback? | |

### Output

`HistoricalData` (`data` resampled to `timeframe`, spread in pips, on the `timezone` clock).

### Steps

- **`METATRADER`:** `table = BuildCleanDataset(source, timeframe, read_file = MetatraderBarFiles.read_frame)`; return `HistoricalData.from_frame(table, timeframe, symbol, spread_unit = POINTS, timezone)`.
- **`HISTDATA`:** `table = BuildCleanDataset(source, timeframe, pattern = "DAT_MT_*.csv", read_file = HistdataBarFiles.read_frame)`; return `HistoricalData.from_frame(table, timeframe, symbol, timezone)`. The bars have no volume and no spread. Any clock is accepted (`histdata` is right; nothing checks it).
- **`DUKASCOPY`:**
  1. `timezone` must be UTC all year (`is_utc`), since epoch timestamps can only be UTC: `CLOCK_NOT_UTC` otherwise.
  2. Progress `Reading Dukascopy {source}...`.
  3. `table = DukascopyBarFiles.read_path(source)`, minus its always-empty `tick_volume` and `volume` columns (so they aren't resampled into zeros).
  4. Return `HistoricalData.from_frame(resample_ohlc(clean_frame(table), timeframe), timeframe, symbol, spread_unit = PRICE, timezone)`.

Resampling to the source's own bar size is a no-op. Asking for a size **finer** than the source cannot be detected here and silently relabels the bars (M5 bars come back labelled `1m`); LoadBacktestConfig prevents it for backtests by checking `simulation.timeframe` against `data_source.timeframe`.

### Errors

| Code | Description |
|---|---|
| `CLOCK_NOT_UTC` | Dukascopy with a non-UTC clock: `Dukascopy bars are UTC (epoch timestamps), not {timezone}`. |
| `NO_USABLE_SOURCE_FILES` | From BuildCleanDataset (`METATRADER`, `HISTDATA`). |
| `DUKASCOPY_*` | From [DukascopyBarFiles](ports/dukascopy-bar-files.md). |
| `NO_BARS`, `MISSING_COLUMNS`, `NON_INTEGRAL_VOLUME`, … | From `HistoricalData` ([invariants](domain-market-data.md#8-historicaldata)), e.g. Dukascopy files with no rows. |

---

## 3. LoadBacktestConfig

Reads a backtest config and checks that its values fit what a backtest can run, so a typo fails before any data is loaded instead of silently falling back to a default.

### Input

| Field | Type | Notes |
|---|---|---|
| `config_path` | `Path` | a JSON file, or a folder holding `backtest.json` |

### Output

`BacktestConfig` ([DTO](ports/backtest-config-source.md#backtestconfig)), with `strategy.parameters` converted to the strategy's field types.

### Steps

1. `file = BacktestConfigSource.find_config_file(config_path)`; `config = BacktestConfigSource.read_config(file)` (the shape checks).
2. `strategy.name` is a key of `STRATEGIES`.
3. `splits` is a `SplitMode` wire value.
4. `data_source.format` is a `SourceFormat` wire value; `data_source.symbol` is in `SYMBOLS` (`by_ticker`); `data_source.timezone` resolves (`timezone_by_name`).
5. `simulation.ambiguity` is an `AmbiguityPolicy` wire value; `simulation.timeframe` and `data_source.timeframe` parse as `SampleSize`; `simulation.timeframe.can_be_resampled_from(data_source.timeframe)`.
6. `strategy.parameters`: every name must be one of the strategy's parameters; convert each value by the parameter's type ([table below](#parameter-conversion)); then construct the strategy once with them, so its own validation runs now (the instance is discarded).
7. Return the config with the converted parameters.

The checks run in this order, and the first failure is returned.

#### Parameter conversion

| Parameter type | JSON value accepted | Becomes |
|---|---|---|
| `T?` (optional) | `null`, or what `T` accepts | `null`, or as `T` |
| `Integer` | a whole number (not `true`/`false`, not `5.0`) | `Integer` |
| `Float` | any number (not `true`/`false`) | `Float` |
| `Boolean` | `true` / `false` | `Boolean` |
| `String` | a string | `String` |
| `LocalTime` | `"HH:MM"` (seconds allowed; ISO 8601, no UTC offset) | a time on the data's clock |
| `ZonedTime` | `"HH:MM <zone>"`: exactly a time and a clock name (`timezone_by_name`) separated by whitespace, e.g. `"08:00 Europe/London"`, `"10:00 broker"` | a time in that zone |
| `TradingSession` | a `SESSIONS` name (`"London"`) | that session |
| anything else | none | `CONFIG_PARAMETER_UNSETTABLE` |

### Helper: `cost_model(cost: CostConfig) -> CostModel`

`SpreadCost(commission_pips)` when `cost.spread`, else `FixedCost(pips = commission_pips)`. A config without `simulation.cost` therefore costs **nothing**, not the domain's 1.7-pip default.

### Errors

Every message is prefixed with the config file's path, `{file}: `.

| Code | Description |
|---|---|
| `CONFIG_*` of BacktestConfigSource | Not found, invalid JSON, unknown key, wrong type, missing key, negative commission ([BacktestConfigSource](ports/backtest-config-source.md)). |
| `CONFIG_INVALID_CHOICE` | `strategy.name`, `splits`, `data_source.format`, `simulation.ambiguity` or a session parameter not among its choices: `"{key}" is "{value}"; choose one of {choices}`. |
| `CONFIG_UNKNOWN_SYMBOL` | `"data_source.symbol": unknown symbol ticker '{ticker}'`. |
| `CONFIG_UNKNOWN_TIMEZONE` | `"data_source.timezone" is "{value}": not "broker", "histdata" or an IANA time zone name such as "UTC" or "America/New_York"`. |
| `CONFIG_INVALID_TIMEFRAME` | `"{key}": {the INVALID_INTERVAL message}`. |
| `CONFIG_TIMEFRAME_NOT_MULTIPLE` | `"simulation.timeframe" {tf} is not a whole multiple of the source's "data_source.timeframe" {source tf}; resampling only coarsens`. |
| `CONFIG_UNKNOWN_PARAMETER` | `"strategy.parameters": {strategy} has no parameter(s) {names}; its parameters: {names, or none}`. |
| `CONFIG_PARAMETER_WRONG_TYPE` | `"strategy.parameters.{key}" must be {a whole number \| a number \| true or false \| a string}, got {value as JSON}`. |
| `CONFIG_PARAMETER_BAD_TIME` | `"strategy.parameters.{key}" must be a time {form}, got {value as JSON}`, where `{form}` is `"HH:MM"` for a `LocalTime` and `"HH:MM <zone>" (e.g. "08:00 Europe/London" or "10:00 broker")` for a `ZonedTime`. |
| `CONFIG_PARAMETER_UNSETTABLE` | `"strategy.parameters.{key}" has type {type}, which a JSON config cannot set`. |
| `CONFIG_PARAMETERS_REJECTED` | The strategy refused the values: `invalid "strategy.parameters" for {strategy}: {the strategy's message}`. |

---

## 4. RecordBacktest

Runs a prepared `Backtest` and records it: the domain result, its provenance (clock, git), the human report and the four result files. The reusable entry point for anything that builds its own `Backtest` (a notebook, a parameter sweep).

### Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `backtest` | `Backtest` | | strategy, data, cost model, ambiguity policy, split mode |
| `out_dir` | `Path` | | overwritten |
| `source` | `String?` | `null` | recorded as `run.json`'s `source` |
| `strategy_name` | `String?` | `null` | recorded as `strategy.name`; the strategy's own `name` (its class name) when absent |
| `now` | RunEnvironment `now` | the real clock | in Python, a parameter of `build_run_info` only |
| `git_commit` | RunEnvironment `git_commit` | the real repository | in Python, a parameter of `build_run_info` only |

### Output: `BacktestRun`

| Field | Type | Notes |
|---|---|---|
| `result` | `BacktestResult` | as `Backtest.run()` returned it |
| `run_info` | `RunInfo` | [DTO](ports/backtest-result-store.md#runinfo) |
| `report` | `String` | the content of `statistics.txt` |
| `paths` | `List<Path>` | the four files written |

### Steps

1. `result = backtest.run()` ([domain-backtest.md](domain-backtest.md#4-backtest-and-the-exit-rules)).
2. `run_info = build_run_info(backtest, result, source, strategy_name, now, git_commit)`: the [RunInfo](ports/backtest-result-store.md#runinfo) fields, from the backtest's strategy, data, cost model and settings, `now()` and `git_commit()`.
3. `report = format_report(result, run_info)`: the text laid out in [external-formats.md](external-formats.md#statisticstxt).
4. `paths = BacktestResultStore.write_results(result, run_info, report, out_dir, price_decimals = data.symbol.price_decimals)`.

### Errors

| Code | Description |
|---|---|
| strategy errors | Raised by `generate_positions`, e.g. `WRONG_CLOCK`, `UNSUPPORTED_TIMEFRAME` ([plugins](plugins/README.md)), or `INVALID_POSITION_LEVELS` from a faulty strategy. |
| `POSITION_NOT_OPEN`, `POSITION_BEFORE_DATA` | A strategy returned a closed position, or one before the first bar. |
| `SPREAD_REQUIRED`, `NO_BAR_AT_ASK_MOMENT` | From `SpreadCost`. |
| `TRADE_DATE_NOT_IN_SPLIT` | A trade on a day the strategy's `split_days` doesn't include. |
| `OUTPUT_WRITE_FAILED` | From BacktestResultStore. |

---

## 5. RunBacktestFromConfig

The whole backtest run the `backtest` CLI performs: config → data → strategy → recorded results.

### Input

| Field | Type | Notes |
|---|---|---|
| `config_path` | `Path` | a JSON file, or a folder holding `backtest.json` |
| `progress` | callback? | |

### Output

`BacktestRun` (as RecordBacktest).

### Steps

1. `config = LoadBacktestConfig(config_path)`.
2. `timeframe = SampleSize.Parse(config.simulation.timeframe)`; `symbol = by_ticker(config.data_source.symbol)`.
3. `data = LoadHistoricalData(config.data_source.path, SourceFormat(config.data_source.format), timeframe, symbol, timezone_by_name(config.data_source.timezone), progress)`.
4. `strategy = STRATEGIES[config.strategy.name](config.strategy.parameters)`; the parameters not given keep the strategy's defaults.
5. `backtest = Backtest(strategy, data, cost_model(config.simulation.cost), AmbiguityPolicy(config.simulation.ambiguity), SplitMode(config.splits))`.
6. Return `RecordBacktest(backtest, config.out, source = "{data_source.path} ({format})", strategy_name = config.strategy.name)`.

### Errors

Those of LoadBacktestConfig, LoadHistoricalData and RecordBacktest.

---

## 6. PrepareBars

Reads any source into one bar table in the MetaTrader export's shape and optionally shifts its clock, resamples it and writes it out. The `read_csv` CLI displays the result, or writes it with `output`; a written file is something `load_mt5` reads back, whatever the source format, which is how the application converts and pre-resamples data.

### Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | | a folder or one file |
| `source_format` | `SourceFormat` | `METATRADER` | |
| `symbol` | `Symbol?` | `null` | required for `DUKASCOPY` |
| `strict` | `Boolean` | `false` | MetaTrader/histdata: a malformed line aborts instead of being skipped |
| `on_skip` | `SkipHandler?` | `null` | |
| `source_timezone` | `TimeZone` | `BROKER_SERVER_TZ` | the clock of the files; used only to shift |
| `target_timezone` | `TimeZone?` | `null` | shift to this clock; `null` keeps the source's |
| `timeframe` | `SampleSize?` | `null` | resample to it; `null` keeps the raw bars |
| `output` | `Path?` | `null` | write the result there |
| `decimals` | `Integer?` | `null` | price decimals for `output` |

### Output: `PreparedBars`

| Field | Type | Notes |
|---|---|---|
| `bars` | `Table<BarRow>` | clean, the MetaTrader shape with only the columns the format has; spread in **points** |
| `file_count` | `Integer` | files read (1 for Dukascopy, read in one call) |

### Steps

1. For `DUKASCOPY`: `symbol` is required (`DUKASCOPY_NEEDS_SYMBOL`) and `source_timezone` must be UTC (`CLOCK_NOT_UTC`).
2. Read:
   - `DUKASCOPY`: `DukascopyBarFiles.read_path(source)` minus `tick_volume` and `volume`; convert the spread to points, `round(spread / symbol.tick_size, 2)` (two places drop the float noise).
   - `METATRADER` / `HISTDATA`: `FileSystem.find_files(source, pattern)` with `*.csv` / `DAT_MT_*.csv` (not recursive); no file is `NO_SOURCE_FILES`. Read each, in name order, with that format's port (`strict`, `on_skip`), and concatenate. Unlike BuildCleanDataset, **one unreadable file aborts** the whole read.
3. An empty table is `NO_BARS_FOUND`.
4. `clean_frame`.
5. If `target_timezone`: `shift_timezone(bars, target_timezone, from_tz = source_timezone)`.
6. If `timeframe`: `resample_ohlc(bars, timeframe)`.
7. If `output`: `MetatraderBarFiles.write_frame(bars, output, decimals)`.

In the Python code steps 1 and 3–7 sit in the CLI's `main()` rather than in a use-case function, contrary to the repo's own rule ([doc/architecture.md §3](../architecture.md#3-inside-an-entry-script)). A rewrite should keep them together in the use case.

### Errors

| Code | Description |
|---|---|
| `DUKASCOPY_NEEDS_SYMBOL` | `--source-format dukascopy needs --source-symbol (its tick size converts the spread to points)`. |
| `CLOCK_NOT_UTC` | `Dukascopy bars are UTC (epoch timestamps), not --source-timezone {clock name}`. |
| `NO_SOURCE_FILES` | `no {pattern} files found at '{source}'`. |
| `NO_BARS_FOUND` | `no bars found at {source}`. |
| `MT_PARSE_ERROR`, `MT_AMBIGUOUS_LAYOUT`, `DUKASCOPY_*`, `FILE_NOT_FOUND` | From the bar ports. |
| `TIMESTAMP_NOT_IN_ZONE` | From `shift_timezone`. |
| `OUTPUT_WRITE_FAILED` | Writing `output`. |

---

## 7. ScanRsiDivergences

Detects RSI divergences on M5 bars resampled from MetaTrader M1 exports: the plain indicator, so its divergences are **not** the `rsi_divergence` plugin's entries (no 30/70 band filter, M5 rather than M15).

### Input

| Field | Type | Default |
|---|---|---|
| `source` | `Path` | a folder of MetaTrader M1 exports or one file |
| `rsi_length` | `Integer` | 14 |
| `pivot_left` | `Integer` | 5 |
| `pivot_right` | `Integer` | 5 |
| `range_lower` | `Integer` | 5 |
| `range_upper` | `Integer` | 60 |
| `include_hidden` | `Boolean` | `false` |
| `progress` | callback? | |

### Output

| Field | Type | Notes |
|---|---|---|
| `bars` | `Table<BarRow>` | the M5 bars scanned |
| `divergences` | `List<Divergence>` | sorted by `end_time` |

### Steps

1. `bars = BuildCleanDataset(source, timeframe = 5m, progress)` (MetaTrader reader).
2. `oscillator = rsi(bars.close, rsi_length)`.
3. `divergences = find_divergences(bars, oscillator, pivot_left, pivot_right, range_lower, range_upper, include_hidden)` ([domain-indicators.md](domain-indicators.md#2-divergence)).

In the Python code these steps are inline in the CLI's `main()`; a rewrite should give them their own function, as above.

### Errors

`NO_USABLE_SOURCE_FILES` from BuildCleanDataset.

---

## 8. CollectDailySessions

The open, high, low and close of each chosen trading session on every day of a source.

### Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | | a folder or one file |
| `source_format` | `SourceFormat` | | |
| `sessions` | `List<TradingSession>` | | |
| `symbol` | `Symbol` | `EURUSD` | |
| `source_timezone` | `TimeZone` | | labels the timestamps; nothing is shifted |
| `progress` | callback? | | |

### Output

`Map<TradingSession, Table<SessionOhlcRow>>`, in `sessions` order; each table has one row per day whose session has at least one bar ([`session_ohlc`](domain-market-data.md#7-bar-table-operations)).

### Steps

1. `data = LoadHistoricalData(source, source_format, timeframe = 1m, symbol, source_timezone, progress)`. At M1 sources' own size the resample is a no-op (a coarser source is relabelled, see LoadHistoricalData).
2. For each session: `session_ohlc(data.data, session, timezone = data.timezone)`.

### Errors

Those of LoadHistoricalData.

---

## 9. ListSymbols

### Input

| Field | Type | Default |
|---|---|---|
| `filter` | `String?` | `null` |

### Output

`List<Symbol>`: every symbol in `SYMBOLS`, sorted by ticker; with `filter`, only those whose ticker or name contains it (case-insensitive).

### Steps

1. Sort `SYMBOLS` by ticker.
2. Keep the matches, when filtering.
3. None left: `NO_MATCHING_SYMBOL`.

### Errors

| Code | Description |
|---|---|
| `NO_MATCHING_SYMBOL` | `no symbol matches '{filter}'`. |
