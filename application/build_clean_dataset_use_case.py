"""Build one clean dataset out of a folder of MT5 exports, in memory.

Pick the source files, resample each M1 export to the target timeframe on its
own, concatenate, and drop the timestamps that overlapping monthly/yearly
exports duplicate.

    from application.build_clean_dataset_use_case import build_clean_dataset

    frame = build_clean_dataset("data/eurusd/1min", progress=print)

Unlike `resample_csv.resample`, this does no file I/O of its own -- it
returns the frame and leaves writing to the caller, which is what makes it
equally usable from a CLI, a notebook and a test. What happened to each file
(rows read, lines skipped, errors) is reported only through `progress`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pandas as pd

from domain.pandas_approach.frames import clean_frame, resample_ohlc
from domain.sample_size import SampleSize
from ports.file_system_access import find_files
from ports.mt5_file_access import read_frame

__all__ = ["build_clean_dataset"]

Progress = Callable[[str], None]


def build_clean_dataset(
    input_directory,
    *,
    timeframe: str | SampleSize = "M5",
    skip_parts: Sequence[str] = (),
    progress: Progress | None = None,
) -> pd.DataFrame:
    """Convert every csv in `input_directory` to `timeframe` bars and merge them.

    Each file is resampled on its own before the pieces are concatenated, so
    peak memory is one month rather than the whole history. A file that fails to
    parse is reported through `progress` and skipped -- one bad export never
    aborts the build. Where two files cover the same timestamp the later-sorted
    one wins.

    skip_parts -- filename fragments that mark a file in the folder as generated
    output rather than a raw export (see `find_files`). Empty by default: a
    caller whose folder mixes the two passes its own list.

    progress -- called with one human-readable line per file; pass `print` for a
    CLI, leave it None for library use.
    """
    files = find_files(input_directory, skip_parts=skip_parts)
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
            source = read_frame(path, strict=False, on_skip=count_skip)
            # The port only parses -- sorting and same-file dedup are this
            # module's decision, so they happen here rather than in the port.
            if not source.empty:
                source = clean_frame(source)
            bars = resample_ohlc(source, timeframe)
        except Exception as exc:  # a bad file must not abort the whole build
            say(f"    ERROR: {exc}")
            continue

        if bars.empty:
            say("    SKIP: no usable rows")
            continue

        skipped_text = f", {skipped:,} unparsable lines skipped" if skipped else ""
        say(f"    OK: {len(source):,} source rows -> {len(bars):,} bars{skipped_text}")
        say(f"        {bars['datetime'].min()} -> {bars['datetime'].max()}")

        pieces.append(bars)

    if not pieces:
        raise RuntimeError("No usable source files. See errors above.")

    return _combine_pieces(pieces, say)


def _combine_pieces(pieces: list[pd.DataFrame], say: Progress) -> pd.DataFrame:
    say("Combining converted pieces...")
    combined = pd.concat(pieces, ignore_index=True)

    count_before = len(combined)
    combined = clean_frame(combined)

    count_after = len(combined)
    removed_count = count_before - count_after

    say(f"Removed {removed_count:,} duplicate timestamps.")
    return combined
