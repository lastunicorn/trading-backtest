# Conventions

The notation every other page of the blueprint uses, and the rules about data that hold everywhere in the application. Read this page first.

## Contents

1. [Type notation](#1-type-notation)
2. [Names](#2-names)
3. [Errors](#3-errors)
4. [Progress reporting](#4-progress-reporting)
5. [Market data rules](#5-market-data-rules)

---

## 1. Type notation

| Notation | Meaning |
|---|---|
| `String` | Text. |
| `Integer` | Signed 64-bit whole number. |
| `Float` | IEEE 754 binary64 (a "double"). Keep it: level comparisons such as `high >= tp` and the statistics must give the same answers as the Python version, and a decimal type would not. `NaN` is allowed only where a page says so. |
| `Boolean` | `true` / `false`. |
| `Date` | A calendar date, no time, no zone. |
| `LocalTime` | A time of day (`HH:MM[:SS]`), no zone. |
| `ZonedTime` | A `LocalTime` plus the `TimeZone` it is read in ("08:00 Europe/London"). Resolving it to an instant needs a date, since the offset depends on the date. |
| `LocalDateTime` | A wall-clock date and time with microsecond precision and **no zone**. Which clock it is on is stated separately, by a `TimeZone` held next to it (see [Clocks](#clocks)). |
| `Instant` | An absolute moment, stored as UTC. |
| `Duration` | A length of time. |
| `TimeZone` | A clock: an IANA zone, or one of the application's own (`ShiftedZone`, `SwitchingZone`); see [domain/market-data.md](domain/market-data.md#3-clocks-time-zones). |
| `Path` | A file-system path. |
| `T?` | A `T` or `null` (absent). |
| `List<T>` | An ordered sequence. |
| `Set<T>` | Distinct values, no order. |
| `Map<K, V>` | Key → value, **in insertion order**: several outputs (statistics rows, `run.json`) depend on it. |
| `Stream<T>` | A lazy sequence, consumed once, in constant memory. |
| `Table<Row>` | Ordered rows, each with the named, typed columns of `Row`. A columnar implementation (a data frame) and a list of records are both fine. |
| `(A, B) -> C` | A function taking `A` and `B` and returning `C`. `-> Void` returns nothing. |
| `Enum` | A closed set of values. Each value is listed with its **wire value** in backticks: the exact string it has in config files, output files and the CLI. |

Defaults are written `= value` after the type (`timeframe: SampleSize = 5m`).

## 2. Names

Properties, actions, parameters, enum values and error codes keep the names they have in the Python code, so every item can be traced back to its source (each section names its Python module). A rewrite may adapt them to its own language's naming conventions (`to_pips` → `toPips`), **except wire names**: config keys, CLI flags, column names of output files, `run.json` keys and enum wire values must stay exactly as written, or existing configs and result files stop working.

## 3. Errors

Each page lists the errors its items can return, as **a short code in `UPPER_SNAKE_CASE` plus a description**. The codes are the blueprint's own names for them: the Python code raises an exception class with a message, and the codes map onto those classes like this:

| Python class | Used for |
|---|---|
| `ValueError` (and subclasses) | invalid input, configuration, data or state: almost every error |
| `FileNotFoundError` | a file or folder that should exist doesn't, or holds no matching file |
| `RuntimeError` | `NO_USABLE_SOURCE_FILES` only, as its subclass `NoUsableSourceFilesError` (`application/build_clean_dataset_use_case.py`) |
| `argparse` usage error | a malformed CLI argument (exit code 2) |

Where the UI prints an error's message to the user, the page gives its wording, with placeholders in `{braces}`. Errors about a config file are prefixed with the file's path (`{file}: ...`).

The CLIs print every expected error as one line, `ERROR: {message}`, to standard error and exit with code 1; see [ui/](ui/README.md#common-behaviour).

## 4. Progress reporting

Long-running use cases take an optional `progress: ((String) -> Void)?` callback and report what they are doing through it, one human-readable line per call. They never print. A CLI passes "print the line"; library callers pass nothing. A use case's result never depends on whether `progress` is given.

## 5. Market data rules

### Bars and the bar table

A **bar** is one OHLC candle: the open, high, low and close price of one interval, and optionally its volumes and spread. A bar is labelled by the moment its interval **starts** (its open time), and is taken to last until the next bar opens: a moment inside a weekend gap belongs to Friday's last bar.

Most of the application works on a **bar table**, `Table<BarRow>`, one bar per row. Its columns, always in this order, the optional ones present only when the source has them:

| Column | Type | Required | Notes |
|---|---|---|---|
| `datetime` | `LocalDateTime` | yes | the bar's open time, on the table's clock |
| `open`, `high`, `low`, `close` | `Float` | yes | bid prices |
| `tick_volume` | `Integer?` | no | number of ticks in the bar |
| `volume` | `Integer?` | no | real (exchange) volume; MetaTrader's `<VOL>` |
| `spread` | `Float?` or `Integer?` | no | its unit depends on the stage, see [Units](#units) |

A table read straight from a source can be unsorted and hold duplicate timestamps. A **clean** table is sorted by `datetime` with no duplicates (`clean_frame`, [domain/market-data.md](domain/market-data.md#7-bar-table-operations)). Everything downstream of loading works on clean tables only, and `HistoricalData` refuses any other.

Extra columns are allowed and pass through untouched.

### Prices are bid

Every price in a bar table is the **bid** price. The ask is bid + spread. Stop-loss and take-profit hits are decided on bid prices; the spread enters only as a cost (`SpreadCost`).

### Units

| Unit | Meaning | Example (EURUSD) |
|---|---|---|
| price | a raw price difference | 0.0010 |
| pip | the symbol's conventional unit, `Symbol.pip_size` | 0.0001 → 1 pip |
| point | the symbol's smallest price step, `Symbol.tick_size` (MetaTrader's spread unit) | 0.00001 → 1 point = 0.1 pip |

Conversions, for a symbol `s`: `pips = price / s.pip_size`, `price = points × s.tick_size`.

The spread column changes unit along the way:

| Stage | Spread unit | Type |
|---|---|---|
| MetaTrader export, MT5 port's table | points | `Integer`, or `Float?` when some rows have none |
| Dukascopy port's table | price (ask − bid) | `Float?` |
| `HistoricalData` (everything the backtest sees) | **pips** | `Float?` |

The loaders convert, using `SpreadUnit` ([domain/market-data.md](domain/market-data.md#8-historicaldata)). All P&L and every statistic is in pips.

### Clocks

Timestamps are **naive** (`LocalDateTime`): a wall-clock reading with no zone attached. The clock they are on is a separate `TimeZone` value carried alongside them (`HistoricalData.timezone`, a `data_source.timezone` config key, a `--source-timezone` CLI flag).

- **Labelling is not shifting.** Saying which clock a table is on changes no timestamp. Only an explicit `shift_timezone` moves them.
- **The clock is never inferred from the file format.** The caller states it.
- A strategy that compares bars with session times converts both to instants (UTC) first, so it works on any clock, across daylight-saving changes.

The sources' clocks, which [domain/market-data.md](domain/market-data.md#3-clocks-time-zones) defines:

| Source | Clock | Name in configs and CLIs |
|---|---|---|
| this repo's MT5 broker exports | New York wall clock + 7 hours (GMT+2 winter, GMT+3 summer, switching on the US dates) | `broker` |
| histdata.com MetaTrader downloads | New York until 2019-01-01, then London − 5 hours | `histdata` |
| Dukascopy | UTC (epoch timestamps) | `UTC` |

### Intervals

Every time window is **half-open**, `[start, end)`: the start belongs to it, the end does not. A bar is "in" a window when its open time is.

### Order and duplicates

Sorting is always **stable**. When two rows claim the same timestamp, the one that came **later** wins (the later row in a table, the later file in name order).

### Missing values

In a table, a missing value is `null` (Python: `NaN`/`NA`/`NaT`). In statistics, an undefined figure (an average of nothing) is `NaN`, written `n/a` in reports and as an empty cell in CSV files.
