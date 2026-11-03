"""MetaTrader exports as pandas DataFrames.

    from libs.metatrader_csv import read_frame, write_frame

    frame = read_frame(path)       # datetime, open, high, low, close[, tick_volume][, volume][, spread]

The file is parsed with `pandas.read_csv` and vectorised coercion, roughly 3x
faster than building a record per line, with the same values and the same
reports of skipped lines as `iterate_records`.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .errors import MetatraderParseError
from .export_layout import DATE_FORMAT, DATETIME_FORMATS, TIME_FORMAT, Layout, sniff_layout
from .records import iterate_records, parse_fields

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

    strict             -- True raises MetatraderParseError on the first unparsable line; False drops it.
    on_skip            -- called as (line_no, line, reason) for each dropped line, exactly as
                          `iterate_records` reports it.
    headerless_layouts -- see `sniff_layout`.
    """
    path = str(path)
    layout = sniff_layout(path, headerless_layouts=headerless_layouts)

    if layout is None:
        return _empty_frame()

    if not layout.has_required_fields:
        # Every line is unparsable: let the record reader raise or report each one.
        for _ in iterate_records(path, strict=strict, on_skip=on_skip, headerless_layouts=headerless_layouts):
            pass
        return _empty_frame()

    keep = [*_PRICE_COLUMNS, *(name for name in _COUNT_COLUMNS if name in layout.columns)]

    # column index -> the name we want that column under in the result
    wanted = {
        layout.columns["date"]: "date",
        layout.columns["time"]: "time",
        **{layout.columns[name]: name for name in keep},
    }
    usecols = sorted(wanted)

    # Blank lines are kept as rows (and dropped below) so that row `i` is
    # always line `first_data_line + i`. A line with extra fields is cut to
    # the layout's width, which is what the record reader does with it too.
    # Every column is read and the wanted ones picked after: the python
    # engine rejects `usecols` when the first line it reads is blank.
    first_data_line = layout.first_row + (1 if layout.has_header else 0)
    raw = pd.read_csv(
        path,
        sep=layout.delimiter,
        header=None,
        names=range(layout.field_count),
        skiprows=first_data_line - 1,
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=False,
        encoding="utf-8-sig",
        encoding_errors="replace",
        engine="python",  # the only engine whose on_bad_lines takes a callable
        on_bad_lines=lambda fields: fields[:layout.field_count],
    )
    raw = raw[usecols].fillna("")  # a short line's missing fields
    raw.columns = [wanted[index] for index in usecols]
    raw = raw.apply(lambda column: column.str.strip())

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

    # A blank line is dropped without a report, as `iterate_records` does.
    blank = raw.eq("").all(axis=1)
    bad_lines = [first_data_line + int(position) for position in np.flatnonzero((bad & ~blank).to_numpy())]

    if strict and bad_lines:
        [(line_no, line, reason)] = _describe_lines(path, layout, bad_lines[:1])
        raise MetatraderParseError(path, line_no, reason, line)

    if on_skip is not None and bad_lines:
        for line_no, line, reason in _describe_lines(path, layout, bad_lines):
            on_skip(line_no, line, reason)

    keep_rows = (~(bad | blank)).to_numpy()
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


def _describe_lines(path: str, layout: Layout, line_numbers: list[int]) -> list[tuple[int, str, str]]:
    """(line_no, line, reason) for each of `line_numbers`, worded as `iterate_records` words them.

    Only the lines that failed are looked at again, so a clean file is read once.
    """
    wanted = set(line_numbers)
    found: dict[int, tuple[str, str]] = {}

    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        for line_no, fields in enumerate(csv.reader(handle, delimiter=layout.delimiter), 1):
            if line_no not in wanted:
                continue

            try:
                parse_fields(fields, layout.columns)
                reason = "unparsable row"  # pandas refused what the record parser accepts
            except ValueError as exc:
                reason = str(exc)

            found[line_no] = (layout.delimiter.join(fields), reason)
            if len(found) == len(wanted):
                break

    return [(line_no, *found[line_no]) for line_no in line_numbers]
