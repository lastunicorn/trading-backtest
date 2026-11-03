# metatrader_csv

Read and write MetaTrader (MT4/MT5) bar exports: the CSVs MetaTrader's "Export bars" produces, and the files other providers ship in the same format (histdata.com's "MetaTrader" downloads, for example).

It depends only on pandas and imports nothing else from this repo, so the folder can be copied into another project unchanged. `records.py` itself uses only the standard library.

## The files

One bar per line: a date, a time, the four prices, then up to three optional fields. They come in two shapes:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>     MT5, with a header
2026.07.01	00:00:00	1.14209	1.14218	1.14166	1.14212	17	0	20

2020.01.02,00:00,1.12112,1.12112,1.12098,1.12098,10                          headerless
```

- **Separator:** comma, tab or semicolon, detected per file.
- **Timestamp:** `YYYY.MM.DD` plus `HH:MM` or `HH:MM:SS`. It is naive: an export doesn't record which clock it is on (usually the broker's server time).
- **Header:** `<DATE>`-style or plain names (`date,time,open,...`), case-insensitive, with a few aliases (`TICKVOL`, `VOL`, `o`/`h`/`l`/`c`, ...).
- **Headerless:** columns are mapped by count, using MetaTrader's full order `DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD` with the tail dropped: 6, 7 and 9 columns are unambiguous. **8 columns is not**: brokers export both `TICKVOL VOL` and `TICKVOL SPREAD`. Reading one raises `AmbiguousLayoutError` unless you say which:

  ```python
  EIGHTH_IS_SPREAD = {8: ("date", "time", "open", "high", "low", "close", "tick_volume", "spread")}
  read_frame(path, headerless_layouts=EIGHTH_IS_SPREAD)
  ```

The fields are named `date`, `time`, `open`, `high`, `low`, `close`, `tick_volume`, `volume` (MetaTrader's real volume, `<VOL>`) and `spread` (in points).

## API

| Name | What it does |
|---|---|
| `iterate_records(path, *, strict=True, on_skip=None, headerless_layouts=None)` | Yields one `MetatraderRecord` per line, streaming. Line numbers given to `on_skip` and in errors are exact. |
| `read_records(...)` | The same, as a list. |
| `read_frame(path, *, strict=True, on_skip=None, headerless_layouts=None)` | One DataFrame: `datetime`, `open`, `high`, `low`, `close` (float64), then whichever of `tick_volume`, `volume`, `spread` the file has (nullable `Int64`). About 3x faster than records, with the same skipped lines and reports. |
| `write_records(records, path, *, decimals=None)` | Writes a headed, comma-separated export; `volume` and `spread` columns only when some record has one. |
| `write_frame(frame, path, *, decimals=None)` | Writes a frame: `datetime` split into `date` and `time`, the other columns as named. |
| `sniff_layout(path, *, headerless_layouts=None)` | The `Layout` (separator, header or not, which column holds which field) from the first row, without parsing the rest. |
| `MetatraderRecord` | `dt`, `open`, `high`, `low`, `close`, `tick_volume`, `volume`, `spread`; the last three `None` when blank or absent. |
| `MetatraderParseError` | A malformed line when reading with `strict=True`: `path`, `line_no`, `reason`, `line`. |

Both writers produce files both readers read back: date as `YYYY.MM.DD`, time as `HH:MM`.

## What reading does and doesn't do

It returns **what the file holds**: rows in file order, a blank volume or spread as `None`/NA (not 0), naive timestamps. It does not sort, remove duplicate timestamps, fill gaps, convert timezones or spread units. Those are the caller's decisions.

A malformed line (a bad number, a timestamp in neither format, missing prices) raises `MetatraderParseError` with `strict=True` (the default). With `strict=False` it is skipped and reported to `on_skip(line_no, line, reason)`. Both readers report the same lines the same way: the exact line number, the line as written and the reason. Blank lines are always skipped silently.
