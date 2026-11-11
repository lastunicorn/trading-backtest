"""Build one clean dataset out of a folder of MetaTrader-style exports, in memory.

Pick the source files, read each one, concatenate them, drop the timestamps
that overlapping monthly/yearly exports duplicate, and resample the merged bars
to the target timeframe.

    from application.build_clean_dataset_use_case import build_clean_dataset

    frame = build_clean_dataset("data/eurusd/1min", progress=print)

It does no file I/O of its own beyond reading -- it returns the frame and
leaves writing to the caller, which is what makes it equally usable from a CLI,
a notebook and a test. What happened to each file
(rows read, lines skipped, errors) is reported only through `progress`.
When no file yields any bars it raises `NoUsableSourceFilesError`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pandas as pd

from domain.market_data.frames import clean_frame, resample_ohlc
from domain.market_data.sample_size import SampleSize
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame

__all__ = ["NoUsableSourceFilesError", "build_clean_dataset"]

Progress = Callable[[str], None]

# Reads one source file into a raw bar frame: (path, *, strict, on_skip) -> frame.
FileReader = Callable[..., pd.DataFrame]


class NoUsableSourceFilesError(RuntimeError):
    """No source file yielded any bars: none was found, or every one failed to read or was empty."""


def build_clean_dataset(
    input_directory,
    *,
    timeframe: str | SampleSize = "M5",
    skip_parts: Sequence[str] = (),
    pattern: str = "*.csv",
    read_file: FileReader = read_frame,
    progress: Progress | None = None,
) -> pd.DataFrame:
    """Merge every csv in `input_directory` and resample it to `timeframe` bars.

    The files' bars are merged *before* resampling, so a bar spanning two files
    (a week across a month boundary) gets both files' data; resampling each file
    on its own would leave two partial bars and keep only one of them. Peak
    memory is therefore the whole source history (about 2.4 million rows for
    six years of M1). A file that fails to parse is reported through `progress`
    and skipped -- one bad export never aborts the build. Where two files cover
    the same timestamp the later-sorted one wins.

    skip_parts -- filename fragments that mark a file in the folder as generated
    output rather than a raw export (see `find_files`). Empty by default: a
    caller whose folder mixes the two passes its own list.

    pattern -- which files in the folder are source files (see `find_files`).

    read_file -- the port that reads one file, called as
    `read_file(path, strict=False, on_skip=...)`. MT5 exports by default;
    `ports.histdata_file_access.read_frame` for histdata downloads.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for library use.
    """
    files = find_files(input_directory, pattern=pattern, skip_parts=skip_parts)
    say = progress or (lambda _message: None)
    say(f"Found {len(files)} candidate source CSV files.")

    pieces: list[pd.DataFrame] = []

    for index, path in enumerate(files, 1):
        say(f"[{index}/{len(files)}] {path.name}")
        skipped = 0

        def count_skip(_line_no: int, _line: str, _reason: str) -> None:
            nonlocal skipped
            skipped += 1

        try:
            source = read_file(path, strict=False, on_skip=count_skip)
        except Exception as exc:  # a bad file must not abort the whole build
            say(f"    ERROR: {exc}")
            continue

        if source.empty:
            say("    SKIP: no usable rows")
            continue

        skipped_text = f", {skipped:,} unparsable lines skipped" if skipped else ""
        say(f"    OK: {len(source):,} rows{skipped_text}")
        say(f"        {source['datetime'].min()} -> {source['datetime'].max()}")

        pieces.append(source)

    if not pieces:
        raise NoUsableSourceFilesError("No usable source files. See errors above.")

    return resample_ohlc(_combine_pieces(pieces, say), timeframe)


def _combine_pieces(pieces: list[pd.DataFrame], say: Progress) -> pd.DataFrame:
    say("Combining the files...")
    combined = pd.concat(pieces, ignore_index=True)

    count_before = len(combined)
    combined = clean_frame(combined)

    count_after = len(combined)
    removed_count = count_before - count_after

    say(f"Removed {removed_count:,} duplicate timestamps.")
    return combined
