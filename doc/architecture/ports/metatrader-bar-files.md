# MetatraderBarFiles

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/mt5_file_access/`.* This repo's MT5 broker exports, and any file in the MetaTrader bar export format ([below](#file-format-metatrader-bar-export)). The one convention it adds to the format: a **headerless 8-column** file, ambiguous in the format, is read as ending in the **spread** (`date, time, open, high, low, close, tick_volume, spread`).

## Actions

| Action | Returns | Description |
|---|---|---|
| `read_frame(path: Path, strict: Boolean = true, on_skip: SkipHandler? = null)` | `Table<RawMt5Row>` | One file, rows in file order. A blank volume is 0; the spread stays `Integer` when every row has one, else `Float?` with nulls. Only the columns the file has. An empty file gives a table with only `datetime`, and so does one without date/time/price columns when not `strict` (with `strict`, its first line is an `MT_PARSE_ERROR`). |
| `iterate_bars(path, strict = true, on_skip = null)` | `Stream<Bar>` | The same lines as `Bar` entities, in constant memory: a blank volume is 0, a missing spread `null`. No use case calls it today. |
| `read_bars(path, strict = true, on_skip = null)` | `List<Bar>` | `iterate_bars` collected. |
| `write_frame(table, path: Path, decimals: Integer? = null)` | `Void` | Writes a bar table as a headed MetaTrader export that `read_frame` reads back ([format](#writing)); creates missing parent folders. `decimals` formats the four prices to that many places. |

`strict` and `on_skip` decide what happens to a malformed line ([what counts as one](#malformed-lines)): with `strict` it is the error `MT_PARSE_ERROR`; without, the line is dropped and reported to `on_skip(line_no, line, reason)`. All readers drop and report exactly the same lines. Blank lines are always skipped silently.

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

## File format: MetaTrader bar export

*Python: `libs/metatrader_csv/` (format), `ports/mt5_file_access/` (this repo's convention).* The CSV MetaTrader 4/5's "Export bars" produces, also used by other providers. One bar per line: a date, a time, the four prices, then up to three optional fields. Two shapes occur:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>        MT5, with a header
2026.07.01	00:00:00	1.14209	1.14218	1.14166	1.14212	17	0	20

2020.01.02,00:00,1.12112,1.12112,1.12098,1.12098,10                             headerless
```

The fields, in MetaTrader's full order: `date`, `time`, `open`, `high`, `low`, `close`, `tick_volume`, `volume` (real volume, `<VOL>`), `spread` (in points). The first six are required.

### Reading

1. **Encoding:** UTF-8; a leading byte-order mark is ignored; undecodable bytes are replaced, never an error.
2. **Separator:** whichever of `,`, tab and `;` occurs most often in the first line; comma on a tie or when none occurs. Fields follow standard CSV quoting (double quotes).
3. **Blank lines** (no field with a non-space character) are skipped silently, anywhere.
4. **The layout is decided once, from the first non-empty row**, for the whole file:
   - It is a **header** when its first field starts with `<`, or normalises to `date` or `datetime` (normalise = trim, strip `<` and `>`, remove spaces, lower-case). Each header field is matched, normalised, against these spellings; the first column matching a field wins, and unknown names are ignored:

     | Field | Header spellings |
     |---|---|
     | `date` | `date` |
     | `time` | `time` |
     | `open`, `high`, `low`, `close` | `open`/`o`, `high`/`h`, `low`/`l`, `close`/`c` |
     | `tick_volume` | `tickvol`, `tickvolume`, `tick_volume` |
     | `volume` | `vol`, `volume`, `realvolume`, `real_volume` |
     | `spread` | `spread` |

     A header that doesn't name all six required fields is ignored: the columns are mapped by position, as below, using its column count. The header row itself is never data.
   - Otherwise the file is **headerless** and columns are mapped by count, MetaTrader's full order with the tail dropped:

     | Columns | Fields |
     |---|---|
     | 6 | `date` … `close` |
     | 7 | + `tick_volume` |
     | 8 | **ambiguous**: + `tick_volume`, `volume` or + `tick_volume`, `spread`. The format can't tell, so the reader must be told which, or it fails (`MT_AMBIGUOUS_LAYOUT`). This repo's MT5 broker exports end in the **spread**. |
     | 9 | + `tick_volume`, `volume`, `spread` |
     | any other | the first *n* fields of the full order (fewer than 6 means every line lacks prices; columns past the ninth are ignored) |
5. **Each data line:**
   - A field past the end of the line counts as blank; fields past the layout's width are ignored.
   - **Timestamp:** `date` (`YYYY.MM.DD`) and `time`, trimmed and joined by a space, read as `YYYY.MM.DD HH:MM`, then as `YYYY.MM.DD HH:MM:SS`. It carries no zone: the file doesn't say which clock it is on.
   - **Prices:** decimal numbers.
   - **Counts** (`tick_volume`, `volume`, `spread`): blank is `null` (not 0); otherwise read as a decimal number and **truncated** toward zero (`10.0` → 10, `12.7` → 12).
6. Rows are returned in file order: no sorting, no deduplication, no filling.

#### Malformed lines

A line is malformed when:

| Problem | Reason reported |
|---|---|
| a required field is blank or missing | `missing field(s): {names, comma-separated}` |
| the timestamp matches neither format | `unrecognized timestamp '{date} {time}'` |
| a price, or a non-blank count, is not a number | the number parser's message (Python: `could not convert string to float: '{text}'`) |

Read strictly, the first malformed line is an error (`MT_PARSE_ERROR`); otherwise it is dropped and reported with its exact line number, its fields re-joined with the separator, and the reason ([SkipHandler](#skiphandler)).

### Writing

1. Comma-separated, UTF-8, `\n` line endings, with a header row.
2. Columns: `date` (`YYYY.MM.DD`), `time` (`HH:MM`; **seconds are dropped**), then every other column of the table, in order, under its own name (`open,high,low,close,tick_volume,volume,spread`).
3. Prices: with `decimals`, fixed-point to that many places; otherwise the shortest decimal text that reads back as the same `Float` (`1.1211`, not `1.12110000000000004`).
4. Other numbers: integers as digits, floats as the shortest round-trip text; `null` is an empty field.

Read back by the MetaTrader reader, a written file gives the same table except for the dropped seconds and the truncated counts (so a fractional spread, such as a Dukascopy spread converted to points, comes back truncated to a whole point).

## Format library: metatrader_csv

*Python: `libs/metatrader_csv/`.* Self-contained code that knows the MetaTrader format and nothing of this application; this port and [HistdataBarFiles](histdata-bar-files.md) use it. A rewrite needs the behaviour, which the [file format](#file-format-metatrader-bar-export) specifies; how it is packaged is free. Its public API, for reference:

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
