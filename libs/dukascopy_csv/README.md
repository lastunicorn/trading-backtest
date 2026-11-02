# dukascopy_csv

Find and read the candle CSVs that [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) downloads from Dukascopy.

It depends only on pandas and imports nothing else from this repo, so the folder can be copied into another project unchanged.

## The files

Each export holds **one price side** of one instrument over one period. Its name is the only place the instrument and side are recorded:

```
<instrument>-<timeframe>-<side>-<start>-<end>.csv

eurusd-m1-bid-2020-01-01-2020-02-01.csv        whole period: end is a date (exclusive)
eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv  partial download: end is the download time
```

The contents are `timestamp,open,high,low,close`, plus `volume` when downloaded with volumes. `timestamp` is epoch milliseconds, UTC.

A bid file and an ask file form a **pair** when they sit in the same folder and share the instrument, timeframe and start date. Their ends can differ, because a partial download's end is the moment that side was downloaded.

## API

```python
from libs.dukascopy_csv import find_files, find_pair, pair_files, read_file

files = find_files("/data/dukascopy/eurusd")      # list[DukascopyFile]: names only, nothing read
pairs = pair_files(files)                          # list[DukascopyFilePair]: .bid / .ask
pair = find_pair(".../eurusd-m1-ask-2026-09-01-2026-09-21T17-14.csv")  # the pair one file belongs to

bid = read_file(pair.bid)                          # DataFrame: datetime (UTC), open, high, low, close[, volume]
```

| Name | What it does |
|---|---|
| `DukascopyFile` | One export, parsed from its name: `path`, `instrument`, `timeframe`, `side` (`PriceSide`), `start`, `end`. `DukascopyFile.parse(path)` returns `None` for a name that isn't an export; `file_name()` builds the name back. |
| `find_files(path)` | Every export under a folder (recursive; other files skipped), or the one export a file path is. Any folder layout works. Sorted by instrument, timeframe, start, side. |
| `pair_files(files)` | Matches bid with ask. Raises `FileNotFoundError` for a file without a partner, `ValueError` for two files on one side of a period. |
| `find_pair(path)` | The pair a single file belongs to, looking for its partner in the same folder. |
| `read_file(file)` | One file's rows. Accepts a `DukascopyFile` or a path. |

## What `read_file` does and doesn't do

It returns **everything the file holds, as stored**: every row in file order, every column. The one change is that `timestamp` becomes a timezone-aware UTC `datetime` column, placed first.

It does not sort, remove duplicates, fill gaps, merge the two sides or compute a spread. Dukascopy's data has known anomalies (a missing trading day on one side, a day of flat filler candles on the other), and they reach the caller unchanged. Deciding what to do about them is the caller's job.

A file missing a required column, or with timestamps that aren't epoch milliseconds, raises `DukascopyFormatError` (a `ValueError`).

Writing exports isn't implemented yet. `DukascopyFile.file_name()` is the naming half a writer would need.
