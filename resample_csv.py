#!/usr/bin/env python3
"""Resample the raw MT5 M1 exports into one clean CSV on a coarser grid.

Step 1 of `eurusd_local_research_v24_2.py` on its own: read every raw export in
a folder, convert each to the target timeframe, merge them, drop the timestamps
that overlapping monthly/yearly exports duplicate, and write the result to a
single file. The research half of v24.2 -- the range/delay/stop/reward grid --
is deliberately absent; this script produces a dataset, not a finding.

    python3 resample_csv.py --source data/eurusd/1min \
        --destination data/eurusd/5min/EURUSD.csv --timeframe M5

`--source`, `--destination` and `--timeframe` are all required -- there are no
defaults. `--source` is either a folder of raw MT5 M1 exports or a single csv
file of M1 bars -- the source data must always be M1.
`--destination` is the CSV to write, with a matching `<name>.report.txt` beside
it, overwritten if it already exists (and saying so); if it points at an existing
directory, the CSV is written inside it as `output_<timeframe>.csv`.

`--destination-timezone` shifts the output's `datetime` column before writing,
treating the source as wall-clock time in `--source-timezone` (default: UTC)
and re-expressing it in `--destination-timezone`. Both are optional; leaving
`--destination-timezone` unset writes the source's own wall clock untouched
(a `--source-timezone` with no `--destination-timezone` has nothing to shift to
and is ignored). Note this default source assumption is UTC, not the
broker-server time the rest of this codebase assumes raw MT5 exports are in --
pass `--source-timezone broker` for broker-server-time sources (New York + 7h,
see `domain.broker_clock`).

    python3 resample_csv.py --source data/eurusd/1min/EURUSD_2020_01.csv \
        --destination scratch/jan.csv --timeframe M5
    python3 resample_csv.py --source data/eurusd/1min \
        --destination data/eurusd/15min/EURUSD.csv --timeframe M15

Each file is resampled on its own before the pieces are concatenated, so peak
memory is one month rather than the whole history. A file that fails to parse
is recorded and skipped -- one bad export never aborts the build. Where two
files cover the same timestamp the later-sorted one wins.

This is tooling, not a research stage: it is versionless and editable. It writes
the same two outputs as `rebuild_clean_m5.py`; that script differs only in taking
an output directory (plus `--name`) rather than a single file path.

Requires pandas (see requirements.txt); activate .venv first.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from domain.pandas_approach.frames import resample_ohlc
from domain.broker_clock import timezone_by_name
from domain.pandas_approach.shift_timezone import shift_timezone
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame, write_frame

# 90-column rules, matching the reports the pipeline scripts print.
WIDTH = 90

# `source_tz` default when a caller asks for `destination_tz` without saying
# what zone the source is in. Deliberately not the codebase-wide broker-server
# default (`shift_timezone`'s own default) -- a raw export is being named here,
# not a pre-shifted frame, so silence on both ends should leave bars untouched,
# and silence on only the source end should get the least surprising guess
# rather than an assumption specific to this data.
DEFAULT_SOURCE_TZ = ZoneInfo("UTC")

# Filename fragments to skip when scanning for source exports, matched
# case-insensitively on any part of the name. Empty by default: the CLI's
# source and destination folders differ, so a re-run never sees its own output.
DEFAULT_SKIP_NAME_PARTS: tuple[str, ...] = ()

# The data-quality report is written beside the CSV, sharing its name with the
# extension swapped for this: `output_M5.csv` -> `output_M5.report.txt`.
REPORT_SUFFIX = ".report.txt"

# CSV filename used when the caller's destination is a directory rather than a
# file path -- `output_M5.csv`, `output_M15.csv`, ... keyed by timeframe.
DEFAULT_CSV_NAME = "output_{timeframe}.csv"

Progress = Callable[[str], None]


@dataclass(frozen=True, slots=True)
class FileStat:
    """What one source file contributed."""

    name: str
    source_rows_count: int
    output_rows_count: int
    first: datetime
    last: datetime
    skipped_lines_count: int = 0


@dataclass(frozen=True, slots=True)
class LoadError:
    """A source file that produced nothing usable."""

    name: str
    reason: str


@dataclass(slots=True)
class ResampleReport:
    """The summary of one `resample()` run.

    The bars themselves are already written to disk, so this carries only the
    numbers a caller reports -- candle count, span, per-file provenance -- plus
    the paths of the two files the run produced.
    """

    candle_count: int
    first_candle_time: datetime
    last_candle_time: datetime
    destination_file_path: Path
    report_path: Path
    stats: list[FileStat] = field(default_factory=list)
    errors: list[LoadError] = field(default_factory=list)
    duplicates_removed_count: int = 0
    timeframe: str = "M5"
    source_tz: tzinfo | None = None
    destination_tz: tzinfo | None = None

    @property
    def skipped_lines_count(self) -> int:
        return sum(stat.skipped_lines_count for stat in self.stats)


def format_quality_report(report: ResampleReport) -> str:
    """Render `report` as the plain-text data-quality report written to disk.

    Same layout as `rebuild_clean_m5.py`: the headline counts, then the
    failed/skipped files, then one line per successful source file.
    """
    label = report.timeframe
    lines = [
        f"CLEAN {label} DATA QUALITY REPORT",
        "=" * WIDTH,
        f"Successful source files: {len(report.stats)}",
        f"Failed/skipped source files: {len(report.errors)}",
        f"Duplicate {label} timestamps removed: {report.duplicates_removed_count:,}",
        f"Final {label} candles: {report.candle_count:,}",
        f"First candle: {report.first_candle_time}",
        f"Last candle: {report.last_candle_time}",
        f"Clean {label} saved at: {report.destination_file_path}",
    ]

    if report.destination_tz is not None:
        lines.append(f"Timezone shift: {report.source_tz} -> {report.destination_tz}")

    if report.skipped_lines_count:
        lines.append(
            f"Unparsable source lines skipped: {report.skipped_lines_count:,}"
        )

    lines += ["", "FAILED/SKIPPED FILES", "-" * WIDTH]
    lines += [f"{error.name} | {error.reason}" for error in report.errors]
    lines += ["", "SUCCESSFUL FILES", "-" * WIDTH]
    lines += [
        f"{stat.name} | source {stat.source_rows_count:,} -> {label} {stat.output_rows_count:,}"
        f" | {stat.first} -> {stat.last}"
        + (f" | {stat.skipped_lines_count:,} lines skipped" if stat.skipped_lines_count else "")
        for stat in report.stats
    ]

    return "\n".join(lines)


def _combine_pieces(pieces: list[pd.DataFrame], say: Progress) -> tuple[pd.DataFrame, int]:
    say("Combining converted pieces...")
    combined = pd.concat(pieces, ignore_index=True).sort_values(
        "datetime", kind="stable"
    )

    count_before = len(combined)
    combined = combined.drop_duplicates("datetime", keep="last").reset_index(drop=True)

    count_after = len(combined)
    removed_count = count_before - count_after

    say(f"Removed {removed_count:,} duplicate timestamps.")
    return combined, removed_count


def resample(
    source_path,
    destination_path,
    *,
    timeframe: str = "M5",
    source_tz: tzinfo | None = None,
    destination_tz: tzinfo | None = None,
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
    progress: Progress | None = None,
) -> ResampleReport:
    """Resample the source M1 csv(s) to `timeframe` bars, merge them, and write
    the result to `destination_path`.

    `source_path` is either a folder of raw M1 exports or a single M1 csv file
    (see `find_files`) -- the source data must always be M1. `destination_path`
    is the csv to write; if it points at an existing directory, the csv is
    written inside it under `DEFAULT_CSV_NAME` (`output_<timeframe>.csv`).

    `destination_tz` shifts `datetime` before resampling, treating each file's
    naive timestamps as wall-clock readings in `source_tz` (default
    `DEFAULT_SOURCE_TZ`, i.e. UTC) and re-expressing them in `destination_tz`,
    naive again (`domain.pandas_approach.shift_timezone`). Leave both `None` to
    keep the source's own wall clock untouched -- the shift only happens when
    `destination_tz` is given; a `source_tz` with no `destination_tz` has
    nothing to shift *to* and is ignored.

    The merged frame is written through the mt5 port, and a data-quality report
    named for it (`REPORT_SUFFIX`: `output_M5.csv` -> `output_M5.report.txt`) is
    written beside it (see `format_quality_report`). The returned
    `ResampleReport` carries the summary numbers and both paths, not the bars.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for silent use.
    """

    say = progress or (lambda _message: None)

    output_file_path = Path(destination_path)

    # A directory destination means "write the CSV in here under a default name".
    if output_file_path.is_dir():
        output_file_path = output_file_path / DEFAULT_CSV_NAME.format(timeframe=timeframe)
        say(f"INFO: Destination is a directory; creating {output_file_path.name} file inside it.")

    if output_file_path.exists():
        say(f"INFO: {output_file_path} already exists and will be overwritten.")

    report_path = output_file_path.with_suffix(REPORT_SUFFIX)

    files = find_files(source_path, skip_parts=skip_parts)

    say(f"Found {len(files)} candidate source CSV files.")

    pieces: list[pd.DataFrame] = []
    stats: list[FileStat] = []
    errors: list[LoadError] = []

    for index, path in enumerate(files, 1):
        say(f"[{index}/{len(files)}] {path.name}")
        skipped = 0

        def count_skip(_line_no: int, _line: str, _reason: str) -> None:
            nonlocal skipped
            skipped += 1

        try:
            source = read_frame(path, strict=False, on_skip=count_skip)
            # The port only parses -- sorting and same-file dedup are this
            # module's decision, so they happen here rather than in the port.
            if not source.empty:
                source = (
                    source.sort_values("datetime", kind="stable")
                    .drop_duplicates("datetime", keep="last")
                    .reset_index(drop=True)
                )
                if destination_tz is not None:
                    source = shift_timezone(
                        source, destination_tz, from_tz=source_tz or DEFAULT_SOURCE_TZ
                    )
            bars = resample_ohlc(source, timeframe)
        except Exception as exc:  # a bad file must not abort the whole build
            say(f"    ERROR: {exc}")
            errors.append(LoadError(path.name, str(exc)))
            continue

        if bars.empty:
            say("    SKIP: no usable rows")
            errors.append(LoadError(path.name, "no usable rows"))
            continue

        first, last = bars["datetime"].min(), bars["datetime"].max()
        say(f"    OK: {len(source):,} source rows -> {len(bars):,} bars")
        say(f"        {first} -> {last}")

        pieces.append(bars)
        stats.append(FileStat(path.name, len(source), len(bars), first, last, skipped))

    if not pieces:
        raise RuntimeError("No usable source files. See errors above.")

    combined, dropped_count = _combine_pieces(pieces, say)

    write_frame(combined, output_file_path)

    report = ResampleReport(
        candle_count=len(combined),
        first_candle_time=combined["datetime"].min(),
        last_candle_time=combined["datetime"].max(),
        destination_file_path=output_file_path,
        report_path=report_path,
        stats=stats,
        errors=errors,
        duplicates_removed_count=dropped_count,
        timeframe=timeframe,
        source_tz=(source_tz or DEFAULT_SOURCE_TZ) if destination_tz is not None else None,
        destination_tz=destination_tz,
    )

    report_path.write_text(format_quality_report(report), encoding="utf-8")
    say(f"Wrote data-quality report: {report_path}")

    return report


def main() -> None:
    start_time = time.perf_counter()
    # Parse command-line arguments.

    args = _parse_args()

    source_path = Path(args.source).resolve()
    destination_path = Path(args.destination).resolve()
    destination_timeframe = args.timeframe

    source_tz = None
    destination_tz = None

    if args.source_timezone:
        try:
            source_tz = timezone_by_name(args.source_timezone)
        except ZoneInfoNotFoundError:
            print(f"ERROR: unknown timezone {args.source_timezone!r}", file=sys.stderr)
            sys.exit(1)

    if args.destination_timezone:
        try:
            destination_tz = timezone_by_name(args.destination_timezone)
        except ZoneInfoNotFoundError:
            print(f"ERROR: unknown timezone {args.destination_timezone!r}", file=sys.stderr)
            sys.exit(1)

    if source_tz is not None and destination_tz is None:
        print("INFO: --source-timezone has no effect without --destination-timezone; ignoring it.")

    print("=" * WIDTH)
    print(f"EURUSD M1 -> {destination_timeframe} RESAMPLER")
    print("=" * WIDTH)
    print("Source:      ", source_path, "(file)" if source_path.is_file() else "(folder)")
    print("Destination: ", destination_path)

    if destination_tz is not None:
        print(f"Timezone:     {args.source_timezone or 'UTC'} -> {args.destination_timezone}")

    # Resample the source M1 data to the desired timeframe and write the output.

    report = resample(
        source_path,
        destination_path,
        timeframe=destination_timeframe,
        source_tz=source_tz,
        destination_tz=destination_tz,
        progress=print,
    )

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

    elapsed = time.perf_counter() - start_time
    print()
    print(f"Total execution time: {elapsed:.2f}s")

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

    parser.add_argument("--source-timezone",
        default=None,
        metavar="TZ",
        help="IANA timezone the source's wall-clock datetimes are in, or "
             "'broker' for MT5 broker-server time (default: UTC). Only takes "
             "effect together with --destination-timezone.")

    parser.add_argument("--destination-timezone",
        default=None,
        metavar="TZ",
        help="IANA timezone to shift datetimes into before writing, e.g. "
             "'UTC', 'Europe/London' (default: no shift, keep the source's "
             "own wall clock).")

    return parser.parse_args()


if __name__ == "__main__":
    main()
