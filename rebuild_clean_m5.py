#!/usr/bin/env python3
"""Rebuild the clean M5 dataset from the raw MT5 M1 exports.

Stage 0 of the pipeline: the loading half of `eurusd_local_research_v24_1.py`,
run on its own. It reads every raw export in a folder, converts each to M5,
merges them, drops duplicate timestamps, and writes the canonical CSV plus a
data-quality report -- the same two outputs v24.1 produced, from the same rules,
now split between `ports/mt5_file_access/` (parsing) and `domain/` (processing).

    python3 rebuild_clean_m5.py --folder data/eurusd/1min --out research_output_v24_1

This is tooling, not a research stage: it produces a dataset, not a finding, so
it is versionless and editable. The v24.1 script stays untouched as the record
of what generated `research_output_v24_1/`; point `--out` at a scratch directory
unless you deliberately mean to regenerate that committed output.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from domain.dataset import CleanDataset, build_clean_dataset

DEFAULT_FOLDER = "data/eurusd/1min"
DEFAULT_OUTDIR = "clean_m5_output"
DEFAULT_NAME = "EURUSD_M5_CLEAN_2020_2026.csv"
REPORT_NAME = "data_quality.txt"

# 90-column rules, matching the v24.1 reports.
WIDTH = 90


def quality_report(dataset: CleanDataset, outpath: Path) -> str:
    label = dataset.timeframe
    lines = [
        f"CLEAN {label} DATA QUALITY REPORT",
        "=" * WIDTH,
        f"Successful source files: {len(dataset.stats)}",
        f"Failed/skipped source files: {len(dataset.errors)}",
        f"Duplicate {label} timestamps removed: {dataset.duplicates_removed_count:,}",
        f"Final {label} candles: {len(dataset.frame):,}",
        f"First candle: {dataset.first}",
        f"Last candle: {dataset.last}",
        f"Clean {label} saved at: {outpath}",
    ]

    if dataset.skipped_lines:
        lines.append(f"Unparsable source lines skipped: {dataset.skipped_lines:,}")

    lines += ["", "FAILED/SKIPPED FILES", "-" * WIDTH]
    lines += [f"{error.name} | {error.reason}" for error in dataset.errors]
    lines += ["", "SUCCESSFUL FILES", "-" * WIDTH]
    lines += [
        f"{stat.name} | source {stat.source_rows_count:,} -> {label} {stat.output_rows_count:,}"
        f" | {stat.first} -> {stat.last}"
        + (f" | {stat.skipped_lines_count:,} lines skipped" if stat.skipped_lines_count else "")
        for stat in dataset.stats
    ]

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="folder of raw MT5 exports")
    parser.add_argument("--out", default=DEFAULT_OUTDIR, help="directory to write into")
    parser.add_argument("--name", default=DEFAULT_NAME, help="filename for the clean CSV")
    parser.add_argument("--timeframe", default="M5", help="broker timeframe label, e.g. M5")
    args = parser.parse_args()

    folder = Path(args.folder).resolve()
    outdir = Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    label = args.timeframe
    print("=" * WIDTH)
    print(f"CLEAN {label} DATASET BUILDER")
    print("=" * WIDTH)
    print("Source folder:", folder)

    dataset = build_clean_dataset(folder, timeframe=args.timeframe, progress=print)

    outpath = outdir / args.name
    dataset.frame.to_csv(outpath, index=False)
    (outdir / REPORT_NAME).write_text(
        quality_report(dataset, outpath), encoding="utf-8"
    )

    print(f"\nClean {label} created:")
    print(outpath)
    print(f"Candles: {len(dataset.frame):,}")
    print(f"Dates: {dataset.first} -> {dataset.last}")
    print(f"Duplicates removed: {dataset.duplicates_removed_count:,}")

    if dataset.skipped_lines:
        print(f"Unparsable lines skipped: {dataset.skipped_lines:,}")

    print("\nDONE.")
    print("Report:", outdir / REPORT_NAME)


if __name__ == "__main__":
    main()
