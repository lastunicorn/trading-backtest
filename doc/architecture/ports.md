# Ports

The use cases' access to everything outside the process: data files, the config file, the result files, the wall clock and git. Each port is listed with its actions, its errors and the DTOs it hands over. The exact file formats are in [external-formats.md](external-formats.md). Types and rules are in [conventions.md](conventions.md).

## Contents

1. [What a port does](#1-what-a-port-does)
2. [MetatraderBarFiles](#2-metatraderbarfiles)
3. [HistdataBarFiles](#3-histdatabarfiles)
4. [DukascopyBarFiles](#4-dukascopybarfiles)
5. [FileSystem](#5-filesystem)
6. [BacktestConfigSource](#6-backtestconfigsource)
7. [RunEnvironment](#7-runenvironment)
8. [BacktestResultStore](#8-backtestresultstore)
9. [DTOs](#9-dtos)
10. [Format libraries](#10-format-libraries)

---

## 1. What a port does

- **A port parses and stops.** It returns what the file holds, in the application's shape. It never sorts, deduplicates, fills, resamples or shifts a clock: those are domain decisions ([domain-market-data.md](domain-market-data.md#7-bar-table-operations)).
- **A port may hand over a domain entity** it parses into (`Bar`), never call domain logic.
- **The format itself lives in a library** ([§10](#10-format-libraries)) that knows nothing of this application; the port adds what is specific to it (which of two ambiguous layouts this broker uses, which columns are noise).
- **Use cases receive ports as parameters** (in Python: functions passed in, such as `read_file`, `now`, `git_commit`), so tests pass fakes. A rewrite should define each port as an interface and inject it.

| Port | Python | Used by |
|---|---|---|
| MetatraderBarFiles | `ports/mt5_file_access/` | BuildCleanDataset, PrepareBars |
| HistdataBarFiles | `ports/histdata_file_access/` | LoadHistoricalData, PrepareBars |
| DukascopyBarFiles | `ports/dukascopy_file_access/` | LoadHistoricalData, PrepareBars |
| FileSystem | `ports/file_system_access/` | BuildCleanDataset, PrepareBars |
| BacktestConfigSource | `ports/backtest_config_access/` | LoadBacktestConfig |
| RunEnvironment | `ports/run_environment/` | RecordBacktest |
| BacktestResultStore | `backtest.py` (`write_results`) | RecordBacktest |

---

## 2. MetatraderBarFiles

*Python: `ports/mt5_file_access/`.* This repo's MT5 broker exports, and any file in the MetaTrader bar export format ([external-formats.md](external-formats.md#1-metatrader-bar-export)). The one convention it adds to the format: a **headerless 8-column** file, ambiguous in the format, is read as ending in the **spread** (`date, time, open, high, low, close, tick_volume, spread`).

### Actions

| Action | Returns | Description |
|---|---|---|
| `read_frame(path: Path, strict: Boolean = true, on_skip: SkipHandler? = null)` | `Table<RawMt5Row>` | One file, rows in file order. A blank volume is 0; the spread stays `Integer` when every row has one, else `Float?` with nulls. Only the columns the file has. An empty file gives a table with only `datetime`, and so does one without date/time/price columns when not `strict` (with `strict`, its first line is an `MT_PARSE_ERROR`). |
| `iterate_bars(path, strict = true, on_skip = null)` | `Stream<Bar>` | The same lines as `Bar` entities, in constant memory: a blank volume is 0, a missing spread `null`. No use case calls it today. |
| `read_bars(path, strict = true, on_skip = null)` | `List<Bar>` | `iterate_bars` collected. |
| `write_frame(table, path: Path, decimals: Integer? = null)` | `Void` | Writes a bar table as a headed MetaTrader export that `read_frame` reads back ([format](external-formats.md#writing)); creates missing parent folders. `decimals` formats the four prices to that many places. |

`strict` and `on_skip` decide what happens to a malformed line ([what counts as one](external-formats.md#malformed-lines)): with `strict` it is the error `MT_PARSE_ERROR`; without, the line is dropped and reported to `on_skip(line_no, line, reason)`. All readers drop and report exactly the same lines. Blank lines are always skipped silently.

### Errors

| Code | Description |
|---|---|
| `MT_PARSE_ERROR` | A malformed line, when `strict`. Carries `path`, `line_no`, `reason`, `line`. Message: `{file name}:{line_no}: {reason}  \|  {line, trimmed, first 80 characters}`. |
| `FILE_NOT_FOUND` | No file at `path` (or unreadable). |

---

## 3. HistdataBarFiles

*Python: `ports/histdata_file_access/`.* histdata.com's MetaTrader downloads ([external-formats.md](external-formats.md#2-histdatacom-download)), read through the same format library. What it adds: the seventh column (a volume histdata always leaves at 0) is dropped, and only `DAT_MT_*.csv` files are sources (each sits beside a `.txt` gap report).

### Constants

| Name | Value | Meaning |
|---|---|---|
| `FILE_PATTERN` | `DAT_MT_*.csv` | which files in a folder are sources |
| `TIMEZONE` | `histdata` | the clock name to use for these files (`HISTDATA_TZ`) |

### Actions

| Action | Returns | Description |
|---|---|---|
| `read_frame(path, strict = true, on_skip = null)` | `Table<RawHistdataRow>` | One file, rows in file order: `datetime` and OHLC only. An empty file gives a table with those columns and no rows. |

### Errors

`MT_PARSE_ERROR`, `FILE_NOT_FOUND`, and `MT_AMBIGUOUS_LAYOUT` for a headerless 8-column file (this port configures no 8-column layout; histdata files have 7).

---

## 4. DukascopyBarFiles

*Python: `ports/dukascopy_file_access/`.* Dukascopy M1 candle exports, which come as one **bid** file and one **ask** file per period ([external-formats.md](external-formats.md#3-dukascopy-candle-export)). What it adds: how a pair becomes one bar.

### Actions

| Action | Returns | Description |
|---|---|---|
| `read_path(path: Path)` | `Table<RawDukascopyRow>` | `path` is a folder (searched **recursively**, so a whole export or one year of it) or either file of a pair. See below. |

Steps:

1. A file: find its pair (the partner in the same folder). A folder: find every export under it and pair them; none is `DUKASCOPY_NO_FILES`.
2. For each pair, in calendar order:
   1. Read both sides; convert `datetime` to a zone-less UTC timestamp; keep `datetime` and OHLC (other columns, such as `volume`, are dropped).
   2. **Left-join** ask onto bid on `datetime`: every bid row is kept, even when the ask side has no row at that moment (a few known dates).
   3. OHLC come from the bid side. `spread` = the mean of `ask − bid` over open, high, low and close, in **price** units; `null` where the ask row is missing.
   4. `tick_volume` and `volume` are added, always `null` (Dukascopy has neither).
3. Concatenate the pairs. No sorting within a file, no deduplication.

### Errors

| Code | Description |
|---|---|
| `DUKASCOPY_NO_FILES` | A folder with no pairs: `no Dukascopy bid/ask files under {path}`. |
| `DUKASCOPY_NOT_FOUND` | `path` doesn't exist: `no Dukascopy export at {path}`. |
| `DUKASCOPY_BAD_NAME` | `path` is a file not named like an export: `{path} is not a Dukascopy export: expected a name like eurusd-m1-bid-2020-01-01-2020-02-01.csv`. |
| `DUKASCOPY_UNPAIRED` | A file whose other side is missing: `Dukascopy file(s) without the other side of their pair: {paths}`. |
| `DUKASCOPY_DUPLICATE_SIDE` | Two files for the same side of one period. |
| `DUKASCOPY_FORMAT_ERROR` | A required column missing, or timestamps that aren't epoch milliseconds. |

---

## 5. FileSystem

*Python: `ports/file_system_access/`.*

| Action | Returns | Description |
|---|---|---|
| `find_files(path: Path, pattern: String = "*.csv", skip_parts: List<String> = [], recursive: Boolean = false)` | `List<Path>` | A file: `[path]`, unfiltered (pointing at a file means that file). A folder: the files matching the glob `pattern` (in subfolders too with `recursive`), minus those whose name contains any of `skip_parts` (case-insensitive), sorted by path. A path that doesn't exist gives an empty list, not an error: callers decide what "no files" means. |

---

## 6. BacktestConfigSource

*Python: `ports/backtest_config_access/`.* Reads the JSON file that drives one backtest and checks its **shape** only: known keys, JSON types, required keys. Whether the values make sense (a registered strategy, a known symbol) is the [LoadBacktestConfig use case](use-cases.md#3-loadbacktestconfig)'s job. The file format is in [external-formats.md](external-formats.md#4-backtest-config-file).

### Constants

`CONFIG_FILE_NAME = "backtest.json"`.

### Actions

| Action | Returns | Description |
|---|---|---|
| `find_config_file(path: Path)` | `Path` | `path` if it is a file; `path/backtest.json` if it is a folder. |
| `read_config(path: Path)` | `BacktestConfig` | See below. |

`read_config`:

1. Find the file; parse it as JSON; the top level must be an object.
2. Check the top-level keys, then `strategy`'s, `data_source`'s, `simulation`'s and `simulation.cost`'s: no unknown key, every value of its JSON type, every required key present ([key table](external-formats.md#keys)).
3. JSON type rules: a JSON boolean is never a number; a whole number is accepted where a number is expected and converted to `Float`.
4. `simulation.cost.commission_pips` must not be negative.
5. Resolve `data_source.path` and `out` against **the config file's folder**, not the working directory, folding `..` away (symbolic links untouched). An absolute path stays as is.
6. `strategy.parameters` is kept as raw JSON values.

### Errors

Every message is prefixed with the config file's path, `{file}: `.

| Code | Description |
|---|---|
| `CONFIG_NOT_FOUND` | `no backtest config at {path}` (a missing file, or a folder without `backtest.json`). |
| `CONFIG_INVALID_JSON` | `not valid JSON: {parser message}`. |
| `CONFIG_NOT_AN_OBJECT` | `expected a JSON object, got {type}`. |
| `CONFIG_UNKNOWN_KEY` | `unknown key(s) {keys}; allowed: {keys}` (nested keys spelled `data_source.path`). |
| `CONFIG_WRONG_TYPE` | `"{key}" must be {a string \| a number \| a whole number \| true or false \| a list \| a JSON object}, got {value as JSON}`. |
| `CONFIG_MISSING_KEY` | `"{key}" is required`. |
| `CONFIG_NEGATIVE_COMMISSION` | `"simulation.cost.commission_pips" cannot be negative, got {value}`. |

---

## 7. RunEnvironment

*Python: `ports/run_environment/`.* The two things a run records about its surroundings.

| Action | Returns | Description |
|---|---|---|
| `now()` | `LocalDateTime` | The local wall-clock time, no zone. |
| `git_commit(repo: Path = the application's own repository)` | `GitCommit` | HEAD's short hash and whether the working tree has uncommitted changes (`git rev-parse --short HEAD`, `git status --porcelain` non-empty). Each field is `null` when git can't tell (not installed, not a repository, a 10-second timeout). Never an error. |

---

## 8. BacktestResultStore

*Python: `backtest.py`'s `write_results`.* In the Python code this lives in the entry script rather than under `ports/`; a rewrite should put it behind a port like the others.

| Action | Returns | Description |
|---|---|---|
| `write_results(result: BacktestResult, run_info: RunInfo, report: String, out_dir: Path, price_decimals: Integer)` | `List<Path>` | Creates `out_dir` if needed and writes, **overwriting**, `positions.csv`, `statistics.txt`, `statistics.csv` and `run.json`, returned in that order. Prices in `positions.csv` are rounded to `price_decimals` (the symbol's), pips to 2 places, `net_r` to 3, `duration_min` to 1. Formats: [external-formats.md](external-formats.md#5-backtest-result-files). |

Errors: `OUTPUT_WRITE_FAILED`, any failure to create the folder or write a file.

---

## 9. DTOs

### Raw bar tables

What each bar port returns: a bar table ([conventions.md](conventions.md#bars-and-the-bar-table)) in file order, possibly unsorted and with duplicates.

| DTO | Columns |
|---|---|
| `RawMt5Row` | `datetime: LocalDateTime`, `open`/`high`/`low`/`close: Float`, then whichever the file has of `tick_volume: Integer` (blank → 0), `volume: Integer` (blank → 0), `spread: Integer` in points (`Float?` when some rows have none) |
| `RawHistdataRow` | `datetime: LocalDateTime`, `open`/`high`/`low`/`close: Float` |
| `RawDukascopyRow` | `datetime: LocalDateTime` (UTC), `open`/`high`/`low`/`close: Float` (bid), `tick_volume: Integer?` (always null), `volume: Integer?` (always null), `spread: Float?` in price units |

### SkipHandler

`(line_no: Integer, line: String, reason: String) -> Void`. Called once per malformed line dropped when reading with `strict = false`. `line_no` is the exact 1-based line number; `line` is the line's fields re-joined with the file's separator; `reason` says what failed (`missing field(s): open, high`, `unrecognized timestamp '…'`, a number that didn't parse).

### GitCommit

| Property | Type | Notes |
|---|---|---|
| `commit` | `String?` | short hash of HEAD |
| `dirty` | `Boolean?` | uncommitted changes in the working tree |

### BacktestConfig

The config file, shape-checked (`read_config`), or value-checked too (`load_backtest_config`, which also types `strategy.parameters`). Field names are the JSON keys.

| Property | Type | Default |
|---|---|---|
| `strategy` | `StrategyConfig` | required |
| `data_source` | `DataSourceConfig` | required |
| `out` | `Path` | required; resolved against the config's folder |
| `simulation` | `SimulationConfig` | all defaults |
| `splits` | `String` (a `SplitMode` wire value) | `none` |

`StrategyConfig`:

| Property | Type | Default |
|---|---|---|
| `name` | `String` (a key of `STRATEGIES`) | required |
| `parameters` | `Map<String, Any>` | `{}`; raw JSON values from `read_config`, the strategy's field types after `load_backtest_config` |

`DataSourceConfig`:

| Property | Type | Default |
|---|---|---|
| `path` | `Path` | required; a file or a folder; resolved against the config's folder |
| `format` | `String` (a `SourceFormat` wire value) | required |
| `symbol` | `String` (a ticker) | required |
| `timeframe` | `String` (a `SampleSize`) | `1m`; the source's bar size as stored |
| `timezone` | `String` (a clock name) | `UTC`; the clock of the source's timestamps |

`SimulationConfig`:

| Property | Type | Default |
|---|---|---|
| `timeframe` | `String` (a `SampleSize`) | `5m`; the bar size to backtest on |
| `ambiguity` | `String` (an `AmbiguityPolicy` wire value) | `exclude` |
| `cost` | `CostConfig` | all defaults: no cost |

`CostConfig`:

| Property | Type | Default |
|---|---|---|
| `spread` | `Boolean` | `false`; charge each trade the spread of its ask-side bar |
| `commission_pips` | `Float` | `0`; charged on every trade; without `spread`, the whole cost |

### RunInfo

The provenance of one backtest run, built by [RecordBacktest](use-cases.md#4-recordbacktest) and written as `run.json`. A JSON object, keys in this order:

| Key | Type | Content |
|---|---|---|
| `created` | `String` | `now()`, ISO 8601 to the second (`2026-11-09T13:21:25`) |
| `strategy.name` | `String` | the config's `strategy.name`, or the strategy's own `name` when none was given |
| `strategy.class` | `String` | the strategy's fully qualified class name (`strategies.narrow_asia_fade.NarrowAsiaFade`) |
| `strategy.parameters` | `Map<String, Any>` | every parameter, in the spelling a config reads back ([recording parameters](plugins.md#recording-parameters)) |
| `data.symbol` | `String` | ticker |
| `data.timeframe` | `String` | `SampleSize` text |
| `data.timezone` | `String` | the clock's **display name** (`broker-server (America/New_York+7h)`, `UTC`) |
| `data.first_bar`, `data.last_bar` | `String` | ISO 8601 (`2020-01-02T00:00:00`) |
| `data.bars` | `Integer` | |
| `simulation.cost_model` | `Map` | `class` (`FixedCost` / `SpreadCost`) followed by its properties (`pips` / `commission_pips`) |
| `simulation.ambiguity_policy` | `String` | wire value |
| `splits` | `String` | wire value |
| `trades` | `Integer` | number of trades |
| `git` | `Map` | `commit`, `dirty` from `GitCommit` |
| `source` | `String` | only when given: `{data_source.path} ({format})` from the CLI |
| `notes` | `List<String>` | only when there are any: `BacktestResult.notes` |

---

## 10. Format libraries

*Python: `libs/metatrader_csv/`, `libs/dukascopy_csv/`.* Self-contained code that knows a file format and nothing of this application; only ports use it. A rewrite needs the behaviour, which [external-formats.md](external-formats.md) specifies; how it is packaged is free. Their public APIs, for reference:

### metatrader_csv

| Item | Description |
|---|---|
| `MetatraderRecord` | `dt: LocalDateTime`, `open`/`high`/`low`/`close: Float`, `tick_volume: Integer?`, `volume: Integer?`, `spread: Integer?` (null when blank or absent; no made-up 0) |
| `Layout` | `delimiter: String`, `columns: Map<String, Integer>` (field → column index), `has_header: Boolean`, `field_count: Integer`, `first_row: Integer`; `has_required_fields` |
| `sniff_layout(path, headerless_layouts?) -> Layout?` | The layout from the first non-empty row, without parsing the rest; `null` for an empty file. `headerless_layouts: Map<Integer, List<String>>` adds or overrides layouts by column count. |
| `iterate_records(path, strict, on_skip, headerless_layouts?) -> Stream<MetatraderRecord>` | Streaming read. |
| `read_records(...) -> List<MetatraderRecord>` | Collected. |
| `read_frame(path, strict, on_skip, headerless_layouts?) -> Table` | Fast table read; volumes and spread `Integer?`. Same lines skipped and reported as `iterate_records`. |
| `write_records(records, path, decimals?)` | Writes a headed export; a `volume` column only when some record has a non-zero one, `spread` only when some record has one. |
| `write_frame(table, path, decimals?)` | Writes a table: `datetime` split into `date` and `time`, the other columns as named. |
| Errors | `MetatraderParseError` (= `MT_PARSE_ERROR`), `AmbiguousLayoutError` (= `MT_AMBIGUOUS_LAYOUT`: `{path}: a headerless 8-column export is ambiguous (TICKVOL VOL or TICKVOL SPREAD); pass headerless_layouts={8: (...)} to say which`) |

### dukascopy_csv

| Item | Description |
|---|---|
| `PriceSide` | Enum `BID` (`bid`), `ASK` (`ask`) |
| `DukascopyFile` | `path`, `instrument: String`, `timeframe: String`, `side: PriceSide`, `start: Date`, `end: Date` (exclusive, a whole period) or `LocalDateTime` (a partial download's time); `parse(path) -> DukascopyFile?` from the name only; `file_name()` builds the name back |
| `DukascopyFilePair` | `bid: DukascopyFile`, `ask: DukascopyFile` |
| `find_files(path) -> List<DukascopyFile>` | Every export under a folder (recursive; other files skipped), or the one export a file is; sorted by instrument, timeframe, start, side, path |
| `pair_files(files) -> List<DukascopyFilePair>` | Matches bid with ask: same folder, instrument, timeframe and start (ends may differ); sorted like `find_files` |
| `find_pair(path) -> DukascopyFilePair` | The pair one file belongs to |
| `read_file(file) -> Table` | Every row and column as stored, `timestamp` (epoch ms) replaced by a UTC `datetime` placed first |
| Errors | `DukascopyFormatError` (= `DUKASCOPY_FORMAT_ERROR`), plus the not-found / bad-name / unpaired / duplicate-side errors of [§4](#4-dukascopybarfiles) |
