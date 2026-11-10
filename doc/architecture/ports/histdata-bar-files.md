# HistdataBarFiles

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/histdata_file_access/`.* histdata.com's MetaTrader downloads ([file format below](#file-format-histdatacom-download)), read through the same format library as [MetatraderBarFiles](metatrader-bar-files.md#format-library-metatrader_csv). What it adds: the seventh column (a volume histdata always leaves at 0) is dropped, and only `DAT_MT_*.csv` files are sources (each sits beside a `.txt` gap report).

## Constants

| Name | Value | Meaning |
|---|---|---|
| `FILE_PATTERN` | `DAT_MT_*.csv` | which files in a folder are sources |
| `TIMEZONE` | `histdata` | the clock name to use for these files (`HISTDATA_TZ`) |

## Actions

| Action | Returns | Description |
|---|---|---|
| `read_frame(path, strict = true, on_skip: SkipHandler? = null)` | `Table<RawHistdataRow>` | One file, rows in file order: `datetime` and OHLC only. An empty file gives a table with those columns and no rows. |

`strict` and `on_skip` work as in [MetatraderBarFiles](metatrader-bar-files.md#actions); `SkipHandler` is described [there](metatrader-bar-files.md#skiphandler).

## Errors

[`MT_PARSE_ERROR` and `FILE_NOT_FOUND`](metatrader-bar-files.md#errors), and `MT_AMBIGUOUS_LAYOUT` for a headerless 8-column file (this port configures no 8-column layout; histdata files have 7).

## DTOs

### RawHistdataRow

A row of the table `read_frame` returns: a bar table ([conventions.md](../conventions.md#bars-and-the-bar-table)) in file order, possibly unsorted and with duplicates.

| Column | Type |
|---|---|
| `datetime` | `LocalDateTime` |
| `open`, `high`, `low`, `close` | `Float` |

## File format: histdata.com download

histdata.com's "MetaTrader" M1 downloads: plain headerless MetaTrader exports, read by the [MetaTrader format's rules](metatrader-bar-files.md#file-format-metatrader-bar-export).

- **Names:** `DAT_MT_{SYMBOL}_M1_{YYYYMM}.csv` (`DAT_MT_EURUSD_M1_202501.csv`). Each sits beside a `.txt` gap report, which is not a source; only names matching `DAT_MT_*.csv` are read.
- **Content:** 7 comma-separated columns, `date`, `time`, `open`, `high`, `low`, `close`, and a volume histdata always leaves at 0, which the port drops. No spread.
- **Clock:** `histdata` (`HISTDATA_TZ`): New York time until 2019-01-01, London − 5 hours from then on. Nothing in the file says so; the config or CLI must.
