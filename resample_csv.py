#!/usr/bin/env python3
"""Resample the raw MT5 M1 exports into one clean M5 CSV.

Step 1 of `eurusd_local_research_v24_2.py` on its own: read every raw export in
a folder, convert each to M5, merge them, drop the timestamps that overlapping
monthly/yearly exports duplicate, and write the result to a single file. The
research half of v24.2 -- the range/delay/stop/reward grid -- is deliberately
absent; this script produces a dataset, not a finding.

    python3 resample_m1_to_m5.py --source data/eurusd/1min \
        --destination data/eurusd/5min/EURUSD.csv --timeframe M5

`--source`, `--destination` and `--timeframe` are all required -- there are no
defaults. `--source` is either a folder of raw MT5 M1 exports or a single csv
file of M1 bars -- the source data must always be M1.
`--destination` is the CSV to write, with a matching `<name>.report.txt` beside
it, overwritten if it already exists (and saying so); if it points at an existing
directory, the CSV is written inside it as `output_<timeframe>.csv`.

    python3 resample_m1_to_m5.py --source data/eurusd/1min/EURUSD_2020_01.csv \
        --destination scratch/jan.csv --timeframe M5
    python3 resample_m1_to_m5.py --source data/eurusd/1min \
        --destination data/eurusd/15min/EURUSD.csv --timeframe M15

This is tooling, not a research stage: it is versionless and editable. It writes
the same two outputs as `rebuild_clean_m5.py`; that script differs only in taking
an output directory (plus `--name`) rather than a single file path.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from application.resample_use_case import resample

# 90-column rules, matching the reports the pipeline scripts print.
WIDTH = 90

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    
    parser.add_argument("--source",
        required=True,
        metavar="PATH",
        help="folder of raw MT5 M1 exports, or a single csv file of M1 bars "
             "(the source data must always be M1)")

    parser.add_argument("--destination",
        required=True,
        help="CSV to write (overwritten if it exists); a directory means "
             "output_<timeframe>.csv inside it")

    parser.add_argument("--timeframe",
        required=True,
        help="broker timeframe label, e.g. M5")
    
    return parser.parse_args()

def main() -> None:
    # Parse command-line arguments.

    args = _parse_args()

    source_path = Path(args.source).resolve()
    destination_path = Path(args.destination).resolve()
    destination_timeframe = args.timeframe

    print("=" * WIDTH)
    print(f"EURUSD M1 -> {destination_timeframe} RESAMPLER")
    print("=" * WIDTH)
    print("Source:      ", source_path, "(file)" if source_path.is_file() else "(folder)")
    print("Destination: ", destination_path)

    # Resample the source M1 data to the desired timeframe and write the output.
    
    report = resample(source_path, destination_path=destination_path, timeframe=destination_timeframe, progress=print)

    # Print summary of the resampling process.

    print(f"\nClean {destination_timeframe} written:")
    print(report.destination_file_path)
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
