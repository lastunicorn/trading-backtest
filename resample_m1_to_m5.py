#!/usr/bin/env python3
"""Resample the raw MT5 M1 exports into one clean M5 CSV.

Step 1 of `eurusd_local_research_v24_2.py` on its own: read every raw export in
a folder, convert each to M5, merge them, drop the timestamps that overlapping
monthly/yearly exports duplicate, and write the result to a single file. The
research half of v24.2 -- the range/delay/stop/reward grid -- is deliberately
absent; this script produces a dataset, not a finding.

    python3 resample_m1_to_m5.py

By default that reads `data/eurusd/1min/` and writes `data/eurusd/5min/EURUSD.csv`
plus a `data_quality.txt` beside it, overwriting the files if they are already
there (and saying so). `--source` also accepts a single csv file, in which case
only that file is processed. Both ends and the timeframe are overridable:

    python3 resample_m1_to_m5.py --source data/eurusd/1min --destination data/eurusd/5min/EURUSD.csv
    python3 resample_m1_to_m5.py --source data/eurusd/1min/EURUSD_2020_01.csv --destination scratch/jan.csv
    python3 resample_m1_to_m5.py --timeframe M15 --destination data/eurusd/15min/EURUSD.csv

This is tooling, not a research stage: it is versionless and editable. It writes
the same two outputs as `rebuild_clean_m5.py`; that script differs only in taking
an output directory (plus `--name`) rather than a single file path.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from application.resample_use_case import resample

DEFAULT_SOURCE = "data/eurusd/1min"
DEFAULT_DESTINATION = "data/eurusd/5min/EURUSD.csv"
DEFAULT_TIMEFRAME = "M5"

# 90-column rules, matching the reports the pipeline scripts print.
WIDTH = 90

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    
    parser.add_argument("--source",
        default=DEFAULT_SOURCE,
        metavar="PATH",
        help="folder of raw MT5 M1 exports, or a single csv file")

    parser.add_argument("--destination",
        default=DEFAULT_DESTINATION,
        help="path of the CSV to write (overwritten if it exists)")
    
    parser.add_argument("--timeframe",
        default=DEFAULT_TIMEFRAME,
        help="broker timeframe label, e.g. M5")
    
    return parser.parse_args()

def main() -> None:
    # Parse command-line arguments.

    args = _parse_args()

    source_path = Path(args.source).resolve()
    output_file_path = Path(args.destination).resolve()
    destination_timeframe = args.timeframe

    print("=" * WIDTH)
    print(f"EURUSD M1 -> {destination_timeframe} RESAMPLER")
    print("=" * WIDTH)
    print("Source:      ", source_path, "(file)" if source_path.is_file() else "(folder)")
    print("Destination: ", output_file_path)

    # Resample the source M1 data to the desired timeframe and write the output.
    
    report = resample(source_path, output_file_path=output_file_path, timeframe=destination_timeframe, progress=print)

    # Print summary of the resampling process.

    print(f"\nClean {destination_timeframe} written:")
    print(output_file_path)
    print(f"Candles: {report.candle_count:,}")
    print(f"Dates: {report.first_candle_time} -> {report.last_candle_time}")
    print(f"Source files: {len(report.stats)} used, {len(report.errors)} skipped")
    print(f"Duplicates removed: {report.duplicates_removed_count:,}")

    if report.skipped_lines_count:
        print(f"Unparsable lines skipped: {report.skipped_lines_count:,}")

    print("\nDONE.")
    print("Report:", report.report_path)


if __name__ == "__main__":
    main()
