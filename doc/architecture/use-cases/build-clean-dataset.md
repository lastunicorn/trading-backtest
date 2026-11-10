# BuildCleanDataset

A [use case](README.md) of the [application blueprint](../README.md).

A folder of exports (or one file) → one clean, resampled bar table, in memory. It merges every file's bars **before** resampling, so a bar spanning two files (a week across a month boundary) gets both files' data. One bad file never aborts the build.

## Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `input_path` | `Path` | | a folder or one file |
| `timeframe` | `SampleSize` | `5m` | the bar size to resample to |
| `skip_parts` | `List<String>` | `[]` | file-name fragments marking generated files to ignore |
| `pattern` | `String` | `*.csv` | which files in the folder are sources |
| `read_file` | a bar port's `read_frame` | MetatraderBarFiles' | called as `read_file(path, strict = false, on_skip)` |
| `progress` | callback? | `null` | |

## Output

`Table<BarRow>`: clean (sorted, no duplicate timestamps) and resampled to `timeframe`.

## Steps

1. `files = FileSystem.find_files(input_path, pattern, skip_parts)`. Progress: `Found {n} candidate source CSV files.`
2. For each file, in name order (`i` from 1):
   1. Progress: `[{i}/{n}] {file name}`.
   2. `read_file(path, strict = false, on_skip = count)`, counting the skipped lines.
   3. If reading fails with any error: progress `    ERROR: {message}`; skip the file.
   4. If the table is empty: progress `    SKIP: no usable rows`; skip the file.
   5. Otherwise progress `    OK: {rows} rows` (plus `, {k} unparsable lines skipped` when `k > 0`; numbers with thousands separators) and `        {first datetime} -> {last datetime}`; keep the table.
3. No table kept: `NO_USABLE_SOURCE_FILES`.
4. Progress `Combining the files...`. Concatenate the tables in file order, then `clean_frame` (so where two files hold the same timestamp, the later file wins). Progress `Removed {k} duplicate timestamps.`
5. Return `resample_ohlc(table, timeframe)`.

Peak memory is the whole source history (about 2.4 million rows for six years of M1).

## Errors

| Code | Description |
|---|---|
| `NO_USABLE_SOURCE_FILES` | No file produced any bar (none found, all unreadable or empty): `No usable source files. See errors above.` |

Per-file errors never escape; they are reported through `progress`.
