# UI

The application's user interface is five command-line programs, one per task, plus a little presentation code they share. A CLI parses and validates its arguments, calls a [use case](use-cases/README.md), prints the result and sets the exit code; it holds no business logic. Types and rules are in [conventions.md](conventions.md).

In the Python code each CLI is an entry script at the repo root (`backtest.py`, …); its `main()` is the UI part.

## Contents

1. [Common behaviour](#1-common-behaviour)
2. [`backtest`](#2-backtest)
3. [`read_csv`](#3-read_csv)
4. [`calculate_daily_sessions`](#4-calculate_daily_sessions)
5. [`rsi_divergence`](#5-rsi_divergence)
6. [`show_symbols`](#6-show_symbols)
7. [Shared presentation](#7-shared-presentation)

---

## 1. Common behaviour

| Exit code | When |
|---|---|
| 0 | success |
| 1 | an expected error: printed as one line, `ERROR: {message}`, on standard error |
| 2 | a malformed argument, rejected by the argument parser before anything runs (usage line plus `{program}: error: {message}`) |

- Progress lines from the use cases go to standard output as they happen.
- `--help` describes every argument.
- Validation happens in two places. The **UI** checks what the argument parser can (types, choices, required arguments) and parses values into domain types (`SampleSize`, `Symbol`, `TimeZone`). Everything that needs the rest of the application (a config's contents, files on disk, a format's clock) is the use case's, and its errors reach the user as `ERROR:` lines.
- Each CLI catches only the errors it expects (listed below); anything else ends the program with a stack trace. A rewrite should report every use-case error as an `ERROR:` line.

---

## 2. `backtest`

*Python: `backtest.py`.* Runs a backtest from a JSON config and writes its results. Use case: [RunBacktestFromConfig](use-cases/run-backtest-from-config.md).

```
backtest <config>
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `config` | `Path` | required | a JSON config file, or a folder holding `backtest.json` |

### Validation

| Input | Rule | On failure |
|---|---|---|
| `config` | given | exit 2 |
| the config's contents | every rule of [LoadBacktestConfig](use-cases/load-backtest-config.md) | `ERROR: {file}: …`, exit 1 |

There is no other UI-level validation: every setting lives in the config, whose format is in [external-formats.md](external-formats.md#4-backtest-config-file).

Errors caught (exit 1): every `ValueError` and `FileNotFoundError` class error, from loading the config, loading the data or running the strategy (wrong clock, missing spread column, missing files). Not caught in the Python code: `NO_USABLE_SOURCE_FILES`, which ends with a stack trace.

### Output

1. The data loader's progress lines.
2. A blank line, then the report: the full content of `statistics.txt` ([format](external-formats.md#statisticstxt)).
3. `Wrote {path}` for each of the four files.
4. A blank line, then `Execution time: {seconds, 2 decimals}s`.

---

## 3. `read_csv`

*Python: `read_csv.py`.* Prints a bar source as a table, raw or processed, or writes the processed bars to a MetaTrader-format CSV. Use case: [PrepareBars](use-cases/prepare-bars.md).

```
read_csv <source> [--source-format F] [--source-timezone TZ] [--source-symbol TICKER]
                  [--timezone TZ] [--timeframe SIZE] [--decimals N]
                  [--rows N] [--all] [--tail] [--output PATH] [--strict]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | required | a file or a folder of exports |
| `--source-format` | `SourceFormat` | `metatrader` | `metatrader`, `histdata` or `dukascopy` |
| `--source-timezone` | `TimeZone` | `broker` | the files' clock; only `--timezone` uses it |
| `--source-symbol` | ticker | none | sets the price decimals; required for `dukascopy` (its tick size converts the spread to points) |
| `--timezone` | `TimeZone` | none | shift the bars to this clock; none keeps the source's |
| `--timeframe` | `SampleSize` text | none | resample; none keeps the raw bars |
| `--decimals` | `Integer` | none | price decimals for display and `--output`; overrides `--source-symbol` |
| `--rows` | `Integer` | 20 | bars shown; a negative value shows none |
| `--all` | flag | off | show every bar (overrides `--rows`) |
| `--tail` | flag | off | show the last bars instead of the first |
| `--output` | `Path` | none | write the full processed table there instead of displaying it (ignores `--rows`/`--all`/`--tail`) |
| `--strict` | flag | off | abort on a malformed line instead of skipping it (`metatrader`, `histdata`; a bad Dukascopy file always aborts) |

### Validation, in order

| Input | Rule | On failure |
|---|---|---|
| `--source-format` | one of the three choices | exit 2 |
| `--decimals`, `--rows` | whole numbers | exit 2 |
| `--timezone`, `--source-timezone` | `timezone_by_name` resolves it ([`timezone_arg`](#timezone_arg)) | exit 2: `argument --timezone: unknown timezone '{name}': expected 'broker', 'histdata' or an IANA name such as 'UTC' or 'Europe/London'` |
| `--timeframe` | parses as `SampleSize` | `ERROR: {INVALID_INTERVAL message}`, exit 1 |
| `--source-symbol` | in `SYMBOLS` | `ERROR: unknown symbol ticker '{ticker}'`, exit 1 |
| `dukascopy` + `--source-symbol` | required | `ERROR:` `DUKASCOPY_NEEDS_SYMBOL`, exit 1 |
| `dukascopy` + `--source-timezone` | UTC all year | `ERROR:` `CLOCK_NOT_UTC`, exit 1 |

Price decimals: `--decimals`, else the symbol's `price_decimals`, else the default number formatting.

Errors caught (exit 1): any error from reading (`NO_SOURCE_FILES`, `MT_PARSE_ERROR` with `--strict`, a bad file), and `NO_BARS_FOUND`.

### Output

```
================================================================
SOURCE: {source}  ({format}, {n} files)          ← ", {n} files" only when n > 1
RESAMPLE: {timeframe}                            ← only with --timeframe
TIMEZONE: {source clock} -> {target clock}       ← only with --timezone
================================================================
Timezone: {clock name the bars are on}
Bars:   {count, thousands separators}
First:  {YYYY.MM.DD HH:MM}
Last:   {YYYY.MM.DD HH:MM}
Span:   {whole days from first to last} days
Skipped: {n} malformed line(s) -- first at line {line_no}: {reason}   ← only when lines were skipped
```

Then, with `--output`, a blank line and `Written: {path}`; otherwise the bar table ([`display_frame`](#display_frame)). Last, a blank line, `Data processing time: {s}s` (reading through resampling) and `Total execution time: {s}s`, both to 2 decimals.

---

## 4. `calculate_daily_sessions`

*Python: `calculate_daily_sessions.py`.* Prints the open, high, low and close of trading sessions for every day of a source. Use case: [CollectDailySessions](use-cases/collect-daily-sessions.md).

```
calculate_daily_sessions [source] [--source-format F] [--session NAME]... [--source-timezone TZ] [--source-symbol TICKER]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | a machine-specific folder (`/nfs/YubabaFinance/trading/historical data/arty/eurusd/1min`) | optional; a rewrite should make it required |
| `--source-format` | `SourceFormat` | `metatrader` | |
| `--session` | a `SESSIONS` name | `Asia` | repeat for several; reported in the order given |
| `--source-timezone` | clock name | `broker` | the files' clock; `UTC` for Dukascopy |
| `--source-symbol` | ticker | `EURUSD` | sets the price decimals |

### Validation

| Input | Rule | On failure |
|---|---|---|
| `--source-format`, `--session` | among the choices | exit 2 |
| `--source-timezone` | `timezone_by_name` resolves it | `ERROR: unknown --source-timezone '{name}'`, exit 1 (checked after parsing, unlike `read_csv`'s exit 2; a rewrite should make them consistent) |
| `--source-symbol` | in `SYMBOLS` | `ERROR: unknown symbol ticker '{ticker}'`, exit 1 |

Errors caught (exit 1): the use case's `ValueError`, `FileNotFoundError` and `RuntimeError` class errors (wrong clock for the format, no source files, nothing readable).

### Output

`Reading {source} ({format}, {clock name} clock)`, the loader's progress lines and a blank line. Then for each session:

```
=== {name} session ({window}, end exclusive) ===
date           open     high      low    close   bars
2020-01-02  1.12112  1.12210  1.12001  1.12150    108
...
  {n} session-days
```

followed by a blank line; or, with no bar in the window, `  (no bars in window)` and a blank line.

- `{window}`: `09:00-18:00 Asia/Tokyo`, or `{start} {zone} - {end} {zone}` when the bounds are in different zones (clock names as `timezone_name` gives them).
- `date` is left-aligned in 10 characters; prices are right-aligned, `price_decimals` places, in the width of the widest formatted high; `bars` right-aligned in 5; columns separated by two spaces.

---

## 5. `rsi_divergence`

*Python: `rsi_divergence.py`.* Prints the RSI divergences found on M5 bars resampled from MetaTrader M1 exports. Use case: [ScanRsiDivergences](use-cases/scan-rsi-divergences.md).

```
rsi_divergence <source> [--rsi-length N] [--pivot-left N] [--pivot-right N] [--range-lower N] [--range-upper N] [--hidden]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | required | a folder of M1 exports, or one file |
| `--rsi-length` | `Integer` | 14 | |
| `--pivot-left` | `Integer` | 5 | |
| `--pivot-right` | `Integer` | 5 | also the confirmation delay |
| `--range-lower` | `Integer` | 5 | minimum bars between two pivots |
| `--range-upper` | `Integer` | 60 | maximum bars between two pivots |
| `--hidden` | flag | off | report hidden divergences too |

### Validation

Only the argument parser's: `source` given, the numbers whole (exit 2). Ranges are not checked (a rewrite should require positive values and `range_lower <= range_upper`). No error is caught: `NO_USABLE_SOURCE_FILES` ends with a stack trace.

### Output

```
==========================================================================================   (90 '=')
EURUSD RSI DIVERGENCE SCAN
==========================================================================================
Source: {source}
{progress lines}

{n} M5 bars, {first datetime} -> {last datetime}

{k} divergence(s) found:
------------------------------------------------------------------------------------------   (90 '-')
{category, left in 8} {direction, left in 8} {start_time} -> {end_time}
...

Execution time: {s}s
```

The heading says EURUSD whatever the data is.

---

## 6. `show_symbols`

*Python: `show_symbols.py`.* Lists the known symbols. Use case: [ListSymbols](use-cases/list-symbols.md).

```
show_symbols [--filter TEXT]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `--filter` | `String` | none | only symbols whose ticker or name contains it (case-insensitive) |

Validation: none beyond the parser. No match: `ERROR: no symbol matches '{filter}'`, exit 1.

Output: a [`format_table`](#format_table) with the columns `TICKER`, `NAME` (left-aligned), `CATEGORY`, `PIP SIZE`, `TICK SIZE`, `DECIMALS`; pip and tick size are printed with the symbol's `price_decimals` places.

---

## 7. Shared presentation

*Python: `ui/`.*

### `timezone_arg`

*`ui/cli_args.py`.* An argument-parser type: `timezone_by_name(text)`, or a usage error `unknown timezone '{name}': expected 'broker', 'histdata' or an IANA name such as 'UTC' or 'Europe/London'`.

### `format_table`

*`ui/text_table.py`.* `format_table(header: List<String>, rows: List<List<String>>, left_align: Set<Integer> = {}) -> List<String>`:

1. Each column's width is the longest of its header and cells.
2. Cells are right-aligned to the width, except the columns in `left_align`.
3. Lines: the header; a rule of `-` the width of each column; then the rows. Columns are separated by two spaces.

### `display_frame`

*`ui/frame_table_view.py`.* `display_frame(table, rows: Integer?, tail: Boolean, decimals: Integer?)` prints a bar table:

1. A blank line, then `--- first {k} bars ---`, `--- last {k} bars ---` (with `tail`) or `--- all bars ---` (`rows` is `null`), where `k` is the number shown.
2. A [`format_table`](#format_table) of the bars shown, columns:

   | Column | Shown when | Cell |
   |---|---|---|
   | `DATE`, `TIME` | always | `YYYY.MM.DD`, `HH:MM` |
   | `OPEN`, `HIGH`, `LOW`, `CLOSE` | always | `decimals` places, or the default number formatting |
   | `TICKVOL` | the table has `tick_volume` | thousands separators |
   | `VOL` | some `volume` is non-zero | thousands separators |
   | `SPREAD` | some `spread` is not null | rounded to a whole number (half to even), blank when null |

3. When bars are hidden: `... {n} more bars (use --all, or --rows N)`.

### The backtest report

`format_report` (*`backtest.py`*) lays out `statistics.txt`, which is also what the `backtest` CLI prints. Its exact layout is in [external-formats.md](external-formats.md#statisticstxt).
