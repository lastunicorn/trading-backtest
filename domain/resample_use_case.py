"""Resample a folder of raw MT5 M1 exports into one clean CSV on a coarser grid.

The M1->M5 build extracted from the pipeline so tooling and future stages share
it instead of re-implementing it: pick the source files, resample each export on
its own, concatenate, drop the timestamps that overlapping monthly/yearly
exports duplicate, and write the merged frame to `output_path`.

    from domain.resample_use_case import resample

    report = resample("data/eurusd/1min", "data/eurusd/5min/EURUSD.csv", progress=print)
    report.candle_count, report.first_candle_time, report.last_candle_time

Unlike `build_clean_dataset`, this writes the CSV itself (through the mt5 port)
and returns only the summary numbers a caller reports -- never the frame.
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
    "resample",
]

# Filename fragments to skip when scanning for source exports, matched
# case-insensitively on any part of the name. Empty by default: the CLI's
# source and destination folders differ, so a re-run never sees its own output.
DEFAULT_SKIP_NAME_PARTS = ()

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
    numbers a caller reports: candle count, span, and per-file provenance.
    """

    candle_count: int
    first_candle_time: datetime
    last_candle_time: datetime
    stats: list[FileStat] = field(default_factory=list)
    errors: list[LoadError] = field(default_factory=list)
    duplicates_removed_count: int = 0
    timeframe: str = "M5"

    @property
    def skipped_lines_count(self) -> int:
        return sum(stat.skipped_lines_count for stat in self.stats)


def _combine_pieces(pieces: list[pd.DataFrame]) -> tuple[pd.DataFrame, int]:
    combined = pd.concat(pieces, ignore_index=True).sort_values(
        "datetime", kind="stable"
    )
    before = len(combined)
    combined = combined.drop_duplicates("datetime", keep="last").reset_index(drop=True)
    return combined, before - len(combined)


def resample(
    input_directory,
    output_path,
    *,
    timeframe: str = "M5",
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
    progress: Progress | None = None,
) -> ResampleReport:
    """Resample every csv in `input_directory` to `timeframe` bars, merge them,
    and write the result to `output_path`.

    Each file is resampled on its own before the pieces are concatenated, so
    peak memory is one month rather than the whole history. A file that fails to
    parse is recorded in `errors` and skipped -- one bad export never aborts the
    build. Where two files cover the same timestamp the later-sorted one wins.

    The merged frame is written to `output_path` through the mt5 port; the
    returned `ResampleReport` carries only the summary numbers, not the bars.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for silent use.
    """

    output_path = Path(output_path)

    files = find_files(input_directory, skip_parts=skip_parts)
    say = progress or (lambda _message: None)
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

    write_frame(combined, output_path)

    return ResampleReport(
        candle_count=len(combined),
        first_candle_time=combined["datetime"].min(),
        last_candle_time=combined["datetime"].max(),
        stats=stats,
        errors=errors,
        duplicates_removed_count=dropped_count,
        timeframe=timeframe,
    )
