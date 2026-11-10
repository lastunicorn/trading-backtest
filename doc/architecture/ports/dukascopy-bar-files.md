# DukascopyBarFiles

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/dukascopy_file_access/`.* Dukascopy M1 candle exports, which come as one **bid** file and one **ask** file per period ([external-formats.md](../external-formats.md#3-dukascopy-candle-export)). What it adds: how a pair becomes one bar.

## Actions

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

## Errors

| Code | Description |
|---|---|
| `DUKASCOPY_NO_FILES` | A folder with no pairs: `no Dukascopy bid/ask files under {path}`. |
| `DUKASCOPY_NOT_FOUND` | `path` doesn't exist: `no Dukascopy export at {path}`. |
| `DUKASCOPY_BAD_NAME` | `path` is a file not named like an export: `{path} is not a Dukascopy export: expected a name like eurusd-m1-bid-2020-01-01-2020-02-01.csv`. |
| `DUKASCOPY_UNPAIRED` | A file whose other side is missing: `Dukascopy file(s) without the other side of their pair: {paths}`. |
| `DUKASCOPY_DUPLICATE_SIDE` | Two files for the same side of one period. |
| `DUKASCOPY_FORMAT_ERROR` | A required column missing, or timestamps that aren't epoch milliseconds. |

## DTOs

### RawDukascopyRow

A row of the table `read_path` returns: a bar table ([conventions.md](../conventions.md#bars-and-the-bar-table)) in file order, possibly unsorted and with duplicates.

| Column | Type | Notes |
|---|---|---|
| `datetime` | `LocalDateTime` | UTC |
| `open`, `high`, `low`, `close` | `Float` | bid |
| `tick_volume` | `Integer?` | always null |
| `volume` | `Integer?` | always null |
| `spread` | `Float?` | price units |

## Format library: dukascopy_csv

*Python: `libs/dukascopy_csv/`.* Self-contained code that knows the Dukascopy export format and nothing of this application; only this port uses it. A rewrite needs the behaviour, which [external-formats.md](../external-formats.md#3-dukascopy-candle-export) specifies; how it is packaged is free. Its public API, for reference:

| Item | Description |
|---|---|
| `PriceSide` | Enum `BID` (`bid`), `ASK` (`ask`) |
| `DukascopyFile` | `path`, `instrument: String`, `timeframe: String`, `side: PriceSide`, `start: Date`, `end: Date` (exclusive, a whole period) or `LocalDateTime` (a partial download's time); `parse(path) -> DukascopyFile?` from the name only; `file_name()` builds the name back |
| `DukascopyFilePair` | `bid: DukascopyFile`, `ask: DukascopyFile` |
| `find_files(path) -> List<DukascopyFile>` | Every export under a folder (recursive; other files skipped), or the one export a file is; sorted by instrument, timeframe, start, side, path |
| `pair_files(files) -> List<DukascopyFilePair>` | Matches bid with ask: same folder, instrument, timeframe and start (ends may differ); sorted like `find_files` |
| `find_pair(path) -> DukascopyFilePair` | The pair one file belongs to |
| `read_file(file) -> Table` | Every row and column as stored, `timestamp` (epoch ms) replaced by a UTC `datetime` placed first |
| Errors | `DukascopyFormatError` (= `DUKASCOPY_FORMAT_ERROR`), plus the not-found / bad-name / unpaired / duplicate-side [errors above](#errors) |
