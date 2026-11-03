"""MT5 exports as the repo's bar frames.

Reading and writing the format is `libs.metatrader_csv`; this module shapes
its frame the way the rest of the repo expects: columns in `FRAME_COLUMNS`
order, a blank volume as 0 (int64), the spread int64 when every row has one
and float with NaN otherwise. Parsing only -- no sorting, no dedup; that stays
a `domain/` decision.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from libs import metatrader_csv
from ports.mt5_file_access.export_conventions import HEADERLESS_LAYOUTS

__all__ = ["FRAME_COLUMNS", "read_frame", "write_frame"]

# Column order of the bar frames used across the repo.
FRAME_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "volume",
    "spread",
)

_VOLUME_COLUMNS = ("tick_volume", "volume")


def read_frame(
    path,
    *,
    strict: bool = False,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> pd.DataFrame:
    """Read one MT5 export into a DataFrame, in file order.

    Columns: `datetime` first, then those of `FRAME_COLUMNS` the export has.
    Prices are float64, `tick_volume`/`volume` int64 (a blank is 0), `spread`
    int64 when every row has one, float64 with NaN otherwise. An empty file,
    or one without date/time/price columns, gives a frame with only `datetime`.

    Defaults to strict=False -- a malformed line is dropped rather than fatal,
    which is how the loader has always treated unparsable rows. Pass `on_skip`
    to count or log them; its `(line_no, line, reason)` are best-effort (see
    `libs.metatrader_csv.read_frame`). Use `iterate_bars` when you need the
    exact per-line detail.
    """
    frame = metatrader_csv.read_frame(path, strict=strict, on_skip=on_skip, headerless_layouts=HEADERLESS_LAYOUTS)

    layout = metatrader_csv.sniff_layout(str(path), headerless_layouts=HEADERLESS_LAYOUTS)
    if layout is None or not layout.has_required_fields:
        return pd.DataFrame(columns=["datetime"])

    for name in _VOLUME_COLUMNS:
        if name in frame.columns:
            frame[name] = frame[name].fillna(0).astype("int64")

    if "spread" in frame.columns:
        complete = frame["spread"].notna().all()
        frame["spread"] = frame["spread"].astype("int64" if complete else "float64")

    return frame[["datetime", *(name for name in FRAME_COLUMNS if name in frame.columns)]]


def write_frame(frame: pd.DataFrame, path: str | Path, *, decimals: int | None = None) -> None:
    """Write a bar frame to a CSV file in MT5 export shape (`libs.metatrader_csv.write_frame`).

    `datetime` becomes `date` (`YYYY.MM.DD`) and `time` (`HH:MM`); every other
    column follows unchanged, in order. `read_frame` reads it back. `decimals`,
    when given, formats open/high/low/close to that many places (e.g. a
    symbol's `price_decimals`).
    """
    metatrader_csv.write_frame(frame, path, decimals=decimals)
