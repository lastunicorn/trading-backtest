"""
combine_csv.py — ad-hoc concatenator for the raw monthly MT5 EURUSD exports.

What it does
------------
1. Globs every CSV under ``data/eurusd/1min/`` (the raw MT5 M1 monthly exports).
2. Reads each one with pandas, trying tab-separated first and falling back to
   comma-separated when the tab parse yields a single column. Files that fail to
   parse are reported and skipped, not fatal.
3. Concatenates all frames, builds a helper ``_datetime`` from the ``<DATE>`` and
   ``<TIME>`` MT5 header columns, sorts chronologically, and drops duplicate
   timestamps (keeping the last occurrence — i.e. the most recently exported
   copy of an overlapping bar).
4. Prints the resulting data range and writes the merged table to
   ``EURUSD_M5_2020_2026.csv`` in the current directory.

If the ``<DATE>``/``<TIME>`` columns are absent (headerless exports), it warns,
lists the columns it did find, and writes the concatenation unsorted and
un-deduplicated.

Usage
-----
    python3 combine_csv.py      # no arguments; paths are hardcoded

Caveats
-------
- **Superseded.** ``eurusd_local_research_v24_1.py`` does this job properly —
  it handles headerless exports, mixed separators, resampling and the
  data-quality report. Use v24.1 for anything that feeds the research pipeline;
  this script is kept only as the earlier ad-hoc version.
- The output filename says *M5* but the input is M1 and **no resampling
  happens here** — the file contains 1-minute bars.
- The self-exclusion filter on line ``f != "EURUSD_M5_2020_2026.csv"`` compares a
  full glob path against a bare filename, so it never matches; it only works
  because the output is written outside the globbed folder.
"""

import pandas as pd
import glob
import os

files = glob.glob("data/eurusd/1min/*.csv")
files = [f for f in files if f != "EURUSD_M5_2020_2026.csv"]

print(f"Found {len(files)} CSV files.")

frames = []

for i, file in enumerate(sorted(files), 1):
    print(f"[{i}/{len(files)}] Reading {file}")

    try:
        df = pd.read_csv(file, sep="\t")

        if len(df.columns) == 1:
            df = pd.read_csv(file)

        df["SOURCE_FILE"] = os.path.basename(file)
        frames.append(df)

    except Exception as e:
        print(f"ERROR reading {file}: {e}")

print("\nCombining...")

combined = pd.concat(frames, ignore_index=True)

if "<DATE>" in combined.columns and "<TIME>" in combined.columns:
    combined["_datetime"] = pd.to_datetime(
        combined["<DATE>"].astype(str) + " " +
        combined["<TIME>"].astype(str),
        errors="coerce"
    )

    combined = combined.sort_values("_datetime")

    before = len(combined)

    combined = combined.drop_duplicates(
        subset=["_datetime"],
        keep="last"
    )

    removed = before - len(combined)

    print(f"Removed {removed:,} duplicate candles.")

    print("\nDATA RANGE")
    print("First candle:", combined["_datetime"].min())
    print("Last candle: ", combined["_datetime"].max())

    combined = combined.drop(columns=["_datetime"])

else:
    print("\nWARNING: Could not find <DATE> and <TIME> columns.")
    print("Columns found:")
    print(list(combined.columns))

combined = combined.drop(columns=["SOURCE_FILE"])

combined.to_csv(
    "EURUSD_M5_2020_2026.csv",
    index=False
)

print("\nDONE")
print(f"Final candles: {len(combined):,}")
print("Created: EURUSD_M5_2020_2026.csv")