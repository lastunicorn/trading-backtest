# PrepareBars

A [use case](README.md) of the [application blueprint](../README.md).

Reads any source into one bar table in the MetaTrader export's shape and optionally shifts its clock, resamples it and writes it out. The `read_csv` CLI displays the result, or writes it with `output`; a written file is something `load_mt5` reads back, whatever the source format, which is how the application converts and pre-resamples data.

## Input

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

## Output: `PreparedBars`

| Field | Type | Notes |
|---|---|---|
| `bars` | `Table<BarRow>` | clean, the MetaTrader shape with only the columns the format has; spread in **points** |
| `file_count` | `Integer` | files read (1 for Dukascopy, read in one call) |

## Steps

1. For `DUKASCOPY`: `symbol` is required (`DUKASCOPY_NEEDS_SYMBOL`) and `source_timezone` must be UTC (`CLOCK_NOT_UTC`).
2. Read:
   - `DUKASCOPY`: `DukascopyBarFiles.read_path(source)` minus `tick_volume` and `volume`; convert the spread to points, `round(spread / symbol.tick_size, 2)` (two places drop the float noise).
   - `METATRADER` / `HISTDATA`: `FileSystem.find_files(source, pattern)` with `*.csv` / `DAT_MT_*.csv` (not recursive); no file is `NO_SOURCE_FILES`. Read each, in name order, with that format's port (`strict`, `on_skip`), and concatenate. Unlike BuildCleanDataset, **one unreadable file aborts** the whole read.
3. An empty table is `NO_BARS_FOUND`.
4. `clean_frame`.
5. If `target_timezone`: `shift_timezone(bars, target_timezone, from_tz = source_timezone)`.
6. If `timeframe`: `resample_ohlc(bars, timeframe)`.
7. If `output`: `MetatraderBarFiles.write_frame(bars, output, decimals)`.

In the Python code steps 1 and 3–7 sit in the CLI's `main()` rather than in a use-case function, contrary to the repo's own rule ([doc/architecture.md §3](../../architecture.md#3-inside-an-entry-script)). A rewrite should keep them together in the use case.

## Errors

| Code | Description |
|---|---|
| `DUKASCOPY_NEEDS_SYMBOL` | `--source-format dukascopy needs --source-symbol (its tick size converts the spread to points)`. |
| `CLOCK_NOT_UTC` | `Dukascopy bars are UTC (epoch timestamps), not --source-timezone {clock name}`. |
| `NO_SOURCE_FILES` | `no {pattern} files found at '{source}'`. |
| `NO_BARS_FOUND` | `no bars found at {source}`. |
| `MT_PARSE_ERROR`, `MT_AMBIGUOUS_LAYOUT`, `DUKASCOPY_*`, `FILE_NOT_FOUND` | From the bar ports. |
| `TIMESTAMP_NOT_IN_ZONE` | From `shift_timezone`. |
| `OUTPUT_WRITE_FAILED` | Writing `output`. |
