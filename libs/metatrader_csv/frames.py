"""MetaTrader exports as pandas DataFrames.

    from libs.metatrader_csv import read_frame, write_frame

    frame = read_frame(path)       # datetime, open, high, low, close[, tick_volume][, volume][, spread]

The file is parsed with `pandas.read_csv` and vectorised coercion, roughly 3x
faster than building a record per line, with the same values.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import MetatraderParseError
from .export_layout import DATE_FORMAT, DATETIME_FORMATS, TIME_FORMAT, Layout, sniff_layout

__all__ = ["read_frame", "write_frame"]

SkipHandler = Callable[[int, str, str], None]

_PRICE_COLUMNS = ("open", "high", "low", "close")
# Whole numbers, nullable: a blank is NA, `10.0` is 10.
_COUNT_COLUMNS = ("tick_volume", "volume", "spread")


def read_frame(
    path: str | Path,
    *,
    strict: bool = True,
    on_skip: SkipHandler | None = None,
    headerless_layouts: Mapping[int, Sequence[str]] | None = None,
) -> pd.DataFrame:
    """Read one export into a DataFrame, rows in file order.

    Columns: `datetime` (naive), open/high/low/close (float64), then whichever
    of tick_volume/volume/spread the export has (nullable Int64, NA where the
    line left it blank). Nothing is sorted, deduplicated or filled. An empty
    file, or one whose rows lack a date, time or price column, gives an empty
    frame with the datetime and price columns.

    strict             -- True raises MetatraderParseError on the first unparsable row; False drops it.
    on_skip            -- called as (line_no, line, reason) for each dropped row. Best-effort,
                          unlike `iterate_records`: line numbers don't count blank lines, a
                          row with the wrong field count is reported as line -1, and `line`
                          shows only the columns read. Use `iterate_records` for exact detail.
    headerless_layouts -- see `sniff_layout`.
    """
    path = str(path)
    layout = sniff_layout(path, headerless_layouts=headerless_layouts)

    if layout is None:
        return _empty_frame()

    if not layout.has_required_fields:
        _report_unusable_rows(path, layout, strict=strict, on_skip=on_skip)
        return _empty_frame()

    keep = [*_PRICE_COLUMNS, *(name for name in _COUNT_COLUMNS if name in layout.columns)]

    # column index -> the name we want that column under in the result
    wanted = {
        layout.columns["date"]: "date",
        layout.columns["time"]: "time",
        **{layout.columns[name]: name for name in keep},
    }
    usecols = sorted(wanted)

    bad_field_counts: list[list[str]] = []

    def handle_bad_line(fields: list[str]):
        if strict:
            raise MetatraderParseError(
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
    raw = raw.apply(lambda column: column.str.strip())

    # First data row's line number, for the approximate line numbers given to `on_skip`.
    line_base = 2 if layout.has_header else 1

    datetime_text = raw["date"] + " " + raw["time"]
    stamp = pd.to_datetime(datetime_text, format=DATETIME_FORMATS[0], errors="coerce")

    # Retry just the rows the first format couldn't read with the next one.
    for fmt in DATETIME_FORMATS[1:]:
        retry = stamp.isna()
        if retry.any():
            stamp = stamp.where(~retry, pd.to_datetime(datetime_text, format=fmt, errors="coerce"))

    values: dict[str, pd.Series] = {}
    bad = stamp.isna()

    for name in keep:
        text = raw[name]
        number = pd.to_numeric(text, errors="coerce")
        values[name] = number

        if name in _PRICE_COLUMNS:
            bad |= number.isna()
        else:  # a blank count is fine; garbage in one is not
            bad |= (text != "") & number.isna()

    # A wholly blank row (every column read is empty) is dropped without a report.
    all_blank = raw.eq("").all(axis=1)
    reportable_positions = np.flatnonzero((bad & ~all_blank).to_numpy())

    if strict and reportable_positions.size:
        first = int(reportable_positions[0])
        raise MetatraderParseError(
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
            column = np.trunc(column.astype("float64")).astype("Int64")
        else:
            column = column.astype("float64")
        frame[name] = column

    return frame


def write_frame(frame: pd.DataFrame, path: str | Path, *, decimals: int | None = None) -> None:
    """Write `frame` as a headed, comma-separated export that `read_frame` reads back.

    The `datetime` column becomes two, `date` (`YYYY.MM.DD`) and `time`
    (`HH:MM`); every other column follows unchanged, in order, under its own
    name. `decimals`, when given, formats open/high/low/close to that many
    places; omitted, they are written in pandas' default float format.
    """
    path = Path(path)

    stamps = pd.to_datetime(frame["datetime"])
    out = frame.drop(columns="datetime")
    out.insert(0, "time", stamps.dt.strftime(TIME_FORMAT))
    out.insert(0, "date", stamps.dt.strftime(DATE_FORMAT))

    if decimals is not None:
        price_columns = [column for column in _PRICE_COLUMNS if column in out.columns]
        out[price_columns] = out[price_columns].map(lambda value: f"{value:.{decimals}f}")

    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(path, index=False)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame({"datetime": pd.Series(dtype="datetime64[us]"),
                         **{name: pd.Series(dtype="float64") for name in _PRICE_COLUMNS}})


def _report_unusable_rows(path: str, layout: Layout, *, strict: bool, on_skip: SkipHandler | None) -> None:
    """Every row of an export whose first row lacks date/time/prices is unparsable: raise on the first, or report each."""
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
        raise MetatraderParseError(path, line_base, "row lacks required date/time/OHLC columns")

    if on_skip is not None:
        for offset in range(len(rows)):
            on_skip(line_base + offset, "", "row lacks required date/time/OHLC columns")
