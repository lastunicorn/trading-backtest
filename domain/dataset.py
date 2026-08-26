"""Build one clean dataset out of a folder of MT5 exports.

The loading half of `eurusd_local_research_v24_1.py`, lifted out so tooling and
future research stages share it instead of re-implementing it: pick the source
files, convert each M1 export to M5 on its own, concatenate, and drop the
timestamps that overlapping monthly/yearly exports duplicate.

    from domain.dataset import build_clean_dataset

    dataset = build_clean_dataset("data/eurusd/1min", progress=print)
    dataset.frame.to_csv("EURUSD_M5_CLEAN_2020_2026.csv", index=False)

It returns data and never prints or writes: reporting is the caller's job, which
is what makes the same function usable from a CLI, a notebook and a test.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from domain.frames import read_frame, resample_ohlc

__all__ = [
    "DEFAULT_SKIP_NAME_PARTS",
    "CleanDataset",
    "FileStat",
    "LoadError",
    "build_clean_dataset",
    "select_sources",
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
    source_rows: int
    output_rows: int
    first: datetime
    last: datetime
    skipped_lines: int = 0


@dataclass(frozen=True, slots=True)
class LoadError:
    """A source file that produced nothing usable."""

    name: str
    reason: str


@dataclass(slots=True)
class CleanDataset:
    """The combined result, plus the numbers a data-quality report needs."""

    frame: pd.DataFrame
    stats: list[FileStat] = field(default_factory=list)
    errors: list[LoadError] = field(default_factory=list)
    duplicates_removed: int = 0

    @property
    def first(self) -> datetime:
        return self.frame["datetime"].min()

    @property
    def last(self) -> datetime:
        return self.frame["datetime"].max()

    @property
    def skipped_lines(self) -> int:
        return sum(stat.skipped_lines for stat in self.stats)


def select_sources(
    folder,
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
) -> list[Path]:
    """The raw exports in `folder`, sorted by name, generated files excluded."""
    lowered = [part.lower() for part in skip_parts]

    return [
        path
        for path in sorted(Path(folder).glob("*.csv"))
        if not any(part in path.name.lower() for part in lowered)
    ]


def build_clean_dataset(
    folder,
    *,
    rule: str = "5min",
    skip_parts: Sequence[str] = DEFAULT_SKIP_NAME_PARTS,
    progress: Progress | None = None,
) -> CleanDataset:
    """Convert every export in `folder` to `rule` bars and merge them.

    Each file is resampled on its own before the pieces are concatenated, so
    peak memory is one month rather than the whole history. A file that fails to
    parse is recorded in `errors` and skipped -- one bad export never aborts the
    build. Where two files cover the same timestamp the later-sorted one wins.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for library use.
    """
    files = select_sources(folder, skip_parts)
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
            bars = resample_ohlc(source, rule)
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
    combined = pd.concat(pieces, ignore_index=True).sort_values(
        "datetime", kind="stable"
    )
    before = len(combined)
    combined = combined.drop_duplicates("datetime", keep="last").reset_index(drop=True)

    return CleanDataset(combined, stats, errors, before - len(combined))
