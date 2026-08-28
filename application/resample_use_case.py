"""Resample raw MT5 M1 exports -- a whole folder, or one file -- into one clean
CSV on a coarser grid.

The M1->M5 build extracted from the pipeline so tooling and future stages share
it instead of re-implementing it: pick the source files, resample each export on
its own, concatenate, drop the timestamps that overlapping monthly/yearly
exports duplicate, and write the merged frame to `destination_path`.

    from application.resample_use_case import resample

    report = resample("data/eurusd/1min", "data/eurusd/5min/EURUSD.csv", progress=print)
    report.candle_count, report.first_candle_time, report.last_candle_time

Two files land next to each other: the merged CSV at `destination_path`, and a
`resample_report.txt` beside it -- the same provenance report `rebuild_clean_m5.py`
writes (failed files, per-file source->output row counts). Unlike
`build_clean_dataset`, this does the writing itself (through the mt5 port) and
returns only the summary numbers a caller reports -- never the frame.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from domain.frames import resample_ohlc
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame, write_frame

__all__ = [
    "ResampleReport",
    "FileStat",
    "LoadError",
    "format_quality_report",
    "resample",
]

# Filename fragments to skip when scanning for source exports, matched
# case-insensitively on any part of the name. Empty by default: the CLI's
# source and destination folders differ, so a re-run never sees its own output.
DEFAULT_SKIP_NAME_PARTS = ()

# Name of the data-quality report, written beside the CSV. Matches the file
# `rebuild_clean_m5.py` produces.
REPORT_NAME = "resample_report.txt"

# CSV filename used when the caller's destination is a directory rather than a
# file path -- `output_M5.csv`, `output_M15.csv`, ... keyed by timeframe.
DEFAULT_CSV_NAME = "output_{timeframe}.csv"

# Column width the report rules use, matching the pipeline's other reports.
_WIDTH = 90

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
        "=" * _WIDTH,
        f"Successful source files: {len(report.stats)}",
        f"Failed/skipped source files: {len(report.errors)}",
        f"Duplicate {label} timestamps removed: {report.duplicates_removed_count:,}",
        f"Final {label} candles: {report.candle_count:,}",
        f"First candle: {report.first_candle_time}",
        f"Last candle: {report.last_candle_time}",
        f"Clean {label} saved at: {report.destination_file_path}",
    ]

    if report.skipped_lines_count:
        lines.append(
            f"Unparsable source lines skipped: {report.skipped_lines_count:,}"
        )

    lines += ["", "FAILED/SKIPPED FILES", "-" * _WIDTH]
    lines += [f"{error.name} | {error.reason}" for error in report.errors]
    lines += ["", "SUCCESSFUL FILES", "-" * _WIDTH]
    lines += [
        f"{stat.name} | source {stat.source_rows_count:,} -> {label} {stat.output_rows_count:,}"
        f" | {stat.first} -> {stat.last}"
        + (f" | {stat.skipped_lines_count:,} lines skipped" if stat.skipped_lines_count else "")
        for stat in report.stats
    ]

    return "\n".join(lines)


def _combine_pieces(pieces: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    combined = pd.concat(pieces, ignore_index=True).sort_values(
        "datetime", kind="stable"
    )
    before = len(combined)
    combined = combined.drop_duplicates("datetime", keep="last").reset_index(drop=True)
    return combined, before - len(combined)


def resample(
    source_path,
    destination_path,
    *,
    timeframe: str = "M5",
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
    progress: Progress | None = None,
) -> ResampleReport:
    """Resample the source csv(s) to `timeframe` bars, merge them, and write the
    result to `destination_path`.

    `source_path` is either a folder of raw exports or a single csv file (see
    `find_files`). `destination_path` is the csv to write; if it points at an
    existing directory, the csv is written inside it under `DEFAULT_CSV_NAME`
    (`output_<timeframe>.csv`).

    Each file is resampled on its own before the pieces are concatenated, so
    peak memory is one month rather than the whole history. A file that fails to
    parse is recorded in `errors` and skipped -- one bad export never aborts the
    build. Where two files cover the same timestamp the later-sorted one wins.

    The merged frame is written through the mt5 port, and a `resample_report.txt`
    (`REPORT_NAME`) is written beside it (see `format_quality_report`). The
    returned `ResampleReport` carries the summary numbers and both paths, not
    the bars.

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

    report_path = output_file_path.with_name(REPORT_NAME)

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

    say("Combining converted pieces...")
    combined, dropped_count = _combine_pieces(pieces)

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
    )

    report_path.write_text(format_quality_report(report), encoding="utf-8")
    say(f"Wrote data-quality report: {report_path}")

    return report
