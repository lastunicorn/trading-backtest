#!/usr/bin/env python3
"""Resample the raw MT5 M1 exports into one clean M5 CSV.

Step 1 of `eurusd_local_research_v24_2.py` on its own: read every raw export in
a folder, convert each to M5, merge them, drop the timestamps that overlapping
monthly/yearly exports duplicate, and write the result to a single file. The
research half of v24.2 -- the range/delay/stop/reward grid -- is deliberately
absent; this script produces a dataset, not a finding.

    python3 resample_m1_to_m5.py

By default that reads `data/eurusd/1min/` and writes `data/eurusd/5min/EURUSD.csv`,
overwriting the file if it is already there (and saying so). Both ends and the
timeframe are overridable:

    python3 resample_m1_to_m5.py --folder data/eurusd/1min --out data/eurusd/5min/EURUSD.csv
    python3 resample_m1_to_m5.py --timeframe M15 --out data/eurusd/15min/EURUSD.csv

This is tooling, not a research stage: it is versionless and editable. For the
canonical dataset the pipeline consumes, see `rebuild_clean_m5.py`, which writes
the same CSV plus a data-quality report.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from domain.dataset import build_clean_dataset
from ports.mt5_file_access import write_frame

DEFAULT_FOLDER = "data/eurusd/1min"
DEFAULT_OUT = "data/eurusd/5min/EURUSD.csv"
DEFAULT_TIMEFRAME = "M5"

# 90-column rules, matching the reports the pipeline scripts print.
WIDTH = 90

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    
    parser.add_argument("--folder",
        default=DEFAULT_FOLDER,
        help="folder of raw MT5 M1 exports")
    
    parser.add_argument("--out",
        default=DEFAULT_OUT,
        help="path of the CSV to write (overwritten if it exists)")
    
    parser.add_argument("--timeframe",
        default=DEFAULT_TIMEFRAME,
        help="broker timeframe label, e.g. M5")
    
    return parser.parse_args()

def main() -> None:
    # Parse command-line arguments.

    args = _parse_args()

    folder = Path(args.folder).resolve()
    outpath = Path(args.out).resolve()
    label = args.timeframe

    print("=" * WIDTH)
    print(f"EURUSD M1 -> {label} RESAMPLER")
    print("=" * WIDTH)
    print("Source folder:", folder)
    print("Destination:  ", outpath)

    if outpath.exists():
        print(f"INFO: {outpath} already exists and will be overwritten.")

    # Build the clean dataset from the raw M1 exports.

    dataset = build_clean_dataset(folder, timeframe=args.timeframe, progress=print)

    # Write the resampled dataset to CSV.

    write_frame(dataset.frame, outpath)

    # Print summary of the resampling process.

    print(f"\nClean {label} written:")
    print(outpath)
    print(f"Candles: {len(dataset.frame):,}")
    print(f"Dates: {dataset.first} -> {dataset.last}")
    print(f"Source files: {len(dataset.stats)} used, {len(dataset.errors)} skipped")
    print(f"Duplicates removed: {dataset.duplicates_removed_count:,}")

    if dataset.skipped_lines:
        print(f"Unparsable lines skipped: {dataset.skipped_lines:,}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
