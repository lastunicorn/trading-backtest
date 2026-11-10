# MetatraderBarFiles

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/mt5_file_access/`.* This repo's MT5 broker exports, and any file in the MetaTrader bar export format ([external-formats.md](../external-formats.md#1-metatrader-bar-export)). The one convention it adds to the format: a **headerless 8-column** file, ambiguous in the format, is read as ending in the **spread** (`date, time, open, high, low, close, tick_volume, spread`).

## Actions

| Action | Returns | Description |
|---|---|---|
| `read_frame(path: Path, strict: Boolean = true, on_skip: SkipHandler? = null)` | `Table<RawMt5Row>` | One file, rows in file order. A blank volume is 0; the spread stays `Integer` when every row has one, else `Float?` with nulls. Only the columns the file has. An empty file gives a table with only `datetime`, and so does one without date/time/price columns when not `strict` (with `strict`, its first line is an `MT_PARSE_ERROR`). |
| `iterate_bars(path, strict = true, on_skip = null)` | `Stream<Bar>` | The same lines as `Bar` entities, in constant memory: a blank volume is 0, a missing spread `null`. No use case calls it today. |
| `read_bars(path, strict = true, on_skip = null)` | `List<Bar>` | `iterate_bars` collected. |
| `write_frame(table, path: Path, decimals: Integer? = null)` | `Void` | Writes a bar table as a headed MetaTrader export that `read_frame` reads back ([format](../external-formats.md#writing)); creates missing parent folders. `decimals` formats the four prices to that many places. |

`strict` and `on_skip` decide what happens to a malformed line ([what counts as one](../external-formats.md#malformed-lines)): with `strict` it is the error `MT_PARSE_ERROR`; without, the line is dropped and reported to `on_skip(line_no, line, reason)`. All readers drop and report exactly the same lines. Blank lines are always skipped silently.

## Errors

| Code | Description |
|---|---|
| `MT_PARSE_ERROR` | A malformed line, when `strict`. Carries `path`, `line_no`, `reason`, `line`. Message: `{file name}:{line_no}: {reason}  \|  {line, trimmed, first 80 characters}`. |
| `FILE_NOT_FOUND` | No file at `path` (or unreadable). |

## DTOs

### RawMt5Row

A row of the table `read_frame` returns: a bar table ([conventions.md](../conventions.md#bars-and-the-bar-table)) in file order, possibly unsorted and with duplicates.

| Column | Type | Notes |
|---|---|---|
| `datetime` | `LocalDateTime` | |
| `open`, `high`, `low`, `close` | `Float` | |
| `tick_volume` | `Integer` | only when the file has it; blank → 0 |
| `volume` | `Integer` | only when the file has it; blank → 0 |
| `spread` | `Integer` in points | only when the file has it; `Float?` when some rows have none |

### SkipHandler

`(line_no: Integer, line: String, reason: String) -> Void`. Called once per malformed line dropped when reading with `strict = false`. `line_no` is the exact 1-based line number; `line` is the line's fields re-joined with the file's separator; `reason` says what failed (`missing field(s): open, high`, `unrecognized timestamp '…'`, a number that didn't parse). [HistdataBarFiles](histdata-bar-files.md) takes it too.

## Format library: metatrader_csv

*Python: `libs/metatrader_csv/`.* Self-contained code that knows the MetaTrader format and nothing of this application; this port and [HistdataBarFiles](histdata-bar-files.md) use it. A rewrite needs the behaviour, which [external-formats.md](../external-formats.md#1-metatrader-bar-export) specifies; how it is packaged is free. Its public API, for reference:

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
