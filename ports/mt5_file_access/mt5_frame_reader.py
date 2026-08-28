from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

from ports.mt5_file_access.mt5_bar_reader import (
    DATETIME_FORMAT,
    BarParseError,
    sniff_layout,
)

__all__ = ["FRAME_COLUMNS", "read_frame", "write_frame"]

# Column order the pipeline's clean CSVs use. `real_volume` is spelled `volume`
# in the frame, the name the research scripts already read.
FRAME_COLUMNS = (
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "volume",
    "spread",
)

# Frame column -> the canonical field name `sniff_layout` reports it under.
_SOURCE_FIELD = {
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "tick_volume": "tick_volume",
    "volume": "real_volume",
    "spread": "spread",
}

# Prices are required and stay float64; a row missing one is unparsable.
_PRICE_COLUMNS = ("open", "high", "low", "close")
# Counts default a blank to 0 and end up int64, matching the old Bar path's
# `int(float(text))`.
_COUNT_COLUMNS = ("tick_volume", "volume")
# `spread` is optional and nullable: a blank becomes NaN, and the column is only
# narrowed to int64 when every row carried one.

# Fields every usable row must place somewhere. Without them there is no bar.
_REQUIRED_SOURCE_FIELDS = ("date", "time", *_PRICE_COLUMNS)


def _strip(frame: pd.DataFrame) -> pd.DataFrame:
    """Trim surrounding whitespace from every cell, as the Bar reader does."""
    return frame.apply(lambda column: column.str.strip())


def read_frame(
    path,
    *,
    strict: bool = False,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> pd.DataFrame:
    """Read one MT5 export into a DataFrame, in file order.

    Parsing only -- no sorting, no dedup; that stays a `domain/` decision.
    Defaults to strict=False -- a malformed line is dropped rather than fatal,
    which is how the loader has always treated unparsable rows. Pass `on_skip`
    to count or log them; it is called once per dropped row, but its
    `(line_no, line, reason)` arguments are best-effort here (line numbers are
    approximate and `line` shows only the columns this reader keeps). Use
    `iter_bars` when you need the exact per-line detail.

    The file is parsed with `pandas.read_csv` and vectorised coercion rather
    than a Bar per row -- roughly 3x faster on the multi-million-row combined
    exports -- but the result is identical: same columns in `FRAME_COLUMNS`
    order, `tick_volume`/`volume` as int64, prices as float64, `datetime` first.
    """
    path = str(path)
    layout = sniff_layout(path)

    if layout is None:  # empty file -- same shape the Bar path returned
        return pd.DataFrame(columns=["datetime"])

    if not all(name in layout.columns for name in _REQUIRED_SOURCE_FIELDS):
        return _no_usable_columns(path, layout, strict=strict, on_skip=on_skip)

    keep = [name for name in FRAME_COLUMNS if _SOURCE_FIELD[name] in layout.columns]

    # column index -> the name we want that column under in the result
    wanted = {
        layout.columns["date"]: "date",
        layout.columns["time"]: "time",
        **{layout.columns[_SOURCE_FIELD[name]]: name for name in keep},
    }
    usecols = sorted(wanted)

    bad_field_counts: list[list[str]] = []

    def handle_bad_line(fields: list[str]):
        if strict:
            raise BarParseError(
                path,
                0,
                f"expected {layout.field_count} fields, got {len(fields)}",
                layout.delimiter.join(fields),
            )
        bad_field_counts.append(fields)
        return None

    raw = pd.read_csv(
        path,
        sep=layout.delimiter,
        header=0 if layout.has_header else None,
        usecols=usecols,
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=True,
        encoding="utf-8-sig",
        encoding_errors="replace",
        engine="python",  # the only engine whose on_bad_lines takes a callable
        on_bad_lines=handle_bad_line,
    )
    raw.columns = [wanted[index] for index in usecols]
    raw = _strip(raw)

    # First non-header data row's line number, so approximate line numbers can
    # be reported to `on_skip`.
    line_base = 2 if layout.has_header else 1

    stamp = pd.to_datetime(
        raw["date"] + " " + raw["time"],
        format=DATETIME_FORMAT,
        errors="coerce",
    )

    values: dict[str, pd.Series] = {}
    bad = stamp.isna()

    for name in keep:
        text = raw[name]
        # A blank count is 0; a blank price or spread coerces straight to NaN.
        source = text.where(text != "", "0") if name in _COUNT_COLUMNS else text
        number = pd.to_numeric(source, errors="coerce")
        values[name] = number

        if name in _PRICE_COLUMNS:
            bad |= number.isna()
        else:  # a blank count/spread is fine; garbage in one is not
            bad |= (text != "") & number.isna()

    # A wholly blank row (every kept column empty) was silently dropped by the
    # Bar reader, never counted. Anything else that failed is a real skip.
    all_blank = raw.eq("").all(axis=1)
    reportable = (bad & ~all_blank).to_numpy()
    reportable_positions = np.flatnonzero(reportable)

    if strict and reportable_positions.size:
        first = int(reportable_positions[0])
        raise BarParseError(
            path,
            line_base + first,
            "unparsable row",
            layout.delimiter.join(map(str, raw.iloc[first])),
        )

    if on_skip is not None:
        for pos in reportable_positions:
            on_skip(
                line_base + int(pos),
                layout.delimiter.join(map(str, raw.iloc[pos])),
                "unparsable row",
            )
        for fields in bad_field_counts:
            on_skip(-1, layout.delimiter.join(fields), "wrong field count")

    keep_rows = (~bad).to_numpy()
    frame = pd.DataFrame({"datetime": stamp[keep_rows].reset_index(drop=True)})

    for name in keep:
        column = values[name][keep_rows].reset_index(drop=True)
        if name in _COUNT_COLUMNS:
            column = np.trunc(column).astype("int64")
        elif name == "spread" and column.notna().all():
            column = np.trunc(column).astype("int64")
        elif name == "spread":
            column = np.trunc(column)
        frame[name] = column

    return frame


def _no_usable_columns(
    path: str,
    layout,
    *,
    strict: bool,
    on_skip: Callable[[int, str, str], None] | None,
) -> pd.DataFrame:
    """Handle an export whose first row lacks date/time/OHLC entirely.

    Every row is unparsable. Matches the Bar reader: raise on the first one when
    strict, otherwise report each to `on_skip` and return an empty frame.
    """
    rows = pd.read_csv(
        path,
        sep=layout.delimiter,
        header=0 if layout.has_header else None,
        usecols=[0],
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=True,
        encoding="utf-8-sig",
        encoding_errors="replace",
        engine="python",
        on_bad_lines="skip",
    )
    line_base = 2 if layout.has_header else 1

    if strict and len(rows):
        raise BarParseError(path, line_base, "row lacks required date/time/OHLC columns")

    if on_skip is not None:
        for offset in range(len(rows)):
            on_skip(line_base + offset, "", "row lacks required date/time/OHLC columns")

    return pd.DataFrame(columns=["datetime"])


def write_frame(frame: pd.DataFrame, path: str | Path) -> None:
    """Write a DataFrame to a CSV file in MT5 export shape.

    The single `datetime` column is split into two: `date` formatted
    `YYYY.MM.DD` and `time` formatted `HH:MM` (no seconds -- the grid is
    minute-aligned). Every other column is written unchanged, in order, after
    them. This is the inverse of `read_frame`: the two columns and their formats
    are exactly what its `%Y.%m.%d %H:%M` parse reads back.
    """
    path = Path(path)

    stamps = pd.to_datetime(frame["datetime"])
    out = frame.drop(columns="datetime")
    out.insert(0, "time", stamps.dt.strftime("%H:%M"))
    out.insert(0, "date", stamps.dt.strftime("%Y.%m.%d"))

    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)
