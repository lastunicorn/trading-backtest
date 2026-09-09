"""Build one clean dataset out of a folder of MT5 exports, in memory.

The use case that turns raw exports into the frame the research pipeline runs
on: pick the source files, resample each M1 export to the target timeframe on
its own, concatenate, and drop the timestamps that overlapping monthly/yearly
exports duplicate.

    from application.build_clean_dataset_use_case import build_clean_dataset

    dataset = build_clean_dataset("data/eurusd/1min", progress=print)
    dataset.frame.to_csv("EURUSD_M5_CLEAN_2020_2026.csv", index=False)

Unlike `resample_use_case.resample`, this does no file I/O of its own -- it
returns the frame plus the counters a data-quality report needs and leaves
writing (and reporting) to the caller, which is what makes it equally usable
from a CLI, a notebook and a test.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from domain.frames import resample_ohlc
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame

__all__ = [
    "DEFAULT_SKIP_NAME_PARTS",
    "CleanDataset",
    "FileStat",
    "LoadError",
    "build_clean_dataset",
]

# Filename fragments that mark a file as something this loader produced (or an
# older tool did), rather than a raw broker export. Matched case-insensitively
# on any part of the name, so a re-run never eats its own output.
DEFAULT_SKIP_NAME_PARTS = (
    "EURUSD_M5_2020_2026",
    "EURUSD_M5_FINAL",
    "EURUSD_M5_LOCAL",
    "EURUSD_M5_CLEAN",
    "combined",
    "combine",
    "research_output",
    "v24_",
)

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
class CleanDataset:
    """The combined result, plus the numbers a data-quality report needs.

    Carries the `timeframe` it was built on (a broker label like "M5") so a
    caller writing a report does not have to keep it alongside the dataset it
    describes.
    """

    frame: pd.DataFrame
    stats: list[FileStat] = field(default_factory=list)
    errors: list[LoadError] = field(default_factory=list)
    duplicates_removed_count: int = 0
    timeframe: str = "M5"

    @property
    def first(self) -> datetime:
        return self.frame["datetime"].min()

    @property
    def last(self) -> datetime:
        return self.frame["datetime"].max()

    @property
    def skipped_lines(self) -> int:
        return sum(stat.skipped_lines_count for stat in self.stats)


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


def build_clean_dataset(
    input_directory,
    *,
    timeframe: str = "M5",
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
    progress: Progress | None = None,
) -> CleanDataset:
    """Convert every csv in `input_directory` to `timeframe` bars and merge them.

    Each file is resampled on its own before the pieces are concatenated, so
    peak memory is one month rather than the whole history. A file that fails to
    parse is recorded in `errors` and skipped -- one bad export never aborts the
    build. Where two files cover the same timestamp the later-sorted one wins.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for library use.
    """
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

    combined, dropped_count = _combine_pieces(pieces, say)

    return CleanDataset(combined, stats, errors, dropped_count, timeframe)
