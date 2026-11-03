"""MetaTrader exports as a stream of records, standard library only.

    from libs.metatrader_csv import iterate_records

    for record in iterate_records(path):       # constant memory, for multi-million-row files
        print(record.dt, record.close, record.spread)

A record holds what its line holds: a field that is blank, or that the export
doesn't have, is None rather than a made-up 0.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .errors import MetatraderParseError
from .export_layout import (
    DATE_FORMAT,
    DATETIME_FORMATS,
    REQUIRED_FIELDS,
    TIME_FORMAT,
    detect_delimiter,
    is_blank,
    layout_of_row,
)

__all__ = ["MetatraderRecord", "iterate_records", "read_records", "write_records"]

SkipHandler = Callable[[int, str, str], None]


@dataclass(frozen=True, slots=True)
class MetatraderRecord:
    """One line of an export. `dt` is naive: an export doesn't say which clock it is on."""

    dt: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: int | None = None
    volume: int | None = None    # MetaTrader's real volume, <VOL>
    spread: int | None = None    # in points


def iterate_records(
    path: str | Path,
    *,
    strict: bool = True,
    on_skip: SkipHandler | None = None,
    headerless_layouts: Mapping[int, Sequence[str]] | None = None,
) -> Iterator[MetatraderRecord]:
    """Yield each record of the export at `path`, in file order. Blank lines are skipped silently.

    strict             -- True raises MetatraderParseError on the first malformed line; False skips it.
    on_skip            -- called as (line_no, line, reason) for each skipped line; line numbers are exact.
    headerless_layouts -- see `sniff_layout`.
    """
    path = str(path)
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()

        if not first_line:
            return

        delimiter = detect_delimiter(first_line)
        handle.seek(0)

        columns: dict[str, int] | None = None

        for line_no, fields in enumerate(csv.reader(handle, delimiter=delimiter), 1):
            if is_blank(fields):
                continue

            if columns is None:
                columns, row_is_header = layout_of_row(fields, headerless_layouts, path)

                if row_is_header:
                    continue  # never treat the header row as data

            try:
                yield parse_fields(fields, columns)
            except ValueError as exc:
                if strict:
                    raise MetatraderParseError(path, line_no, str(exc), delimiter.join(fields)) from exc

                if on_skip is not None:
                    on_skip(line_no, delimiter.join(fields), str(exc))


def read_records(
    path: str | Path,
    *,
    strict: bool = True,
    on_skip: SkipHandler | None = None,
    headerless_layouts: Mapping[int, Sequence[str]] | None = None,
) -> list[MetatraderRecord]:
    """`iterate_records` as a list: fine for one monthly export (~31k records)."""
    return list(iterate_records(path, strict=strict, on_skip=on_skip, headerless_layouts=headerless_layouts))


def write_records(records: Iterable[MetatraderRecord], path: str | Path, *, decimals: int | None = None) -> None:
    """Write `records` as a headed, comma-separated export that `iterate_records` reads back.

    Columns: date (`YYYY.MM.DD`), time (`HH:MM`), open, high, low, close,
    tick_volume, then `volume` only when a record has a non-zero one and
    `spread` only when a record has one. A missing value is written blank.

    `decimals`, when given, formats the four prices to that many places;
    omitted, they are written as Python's `str(float)`.
    """
    path = Path(path)
    records = list(records)

    has_volume = any(record.volume for record in records)
    has_spread = any(record.spread is not None for record in records)

    header = ["date", "time", "open", "high", "low", "close", "tick_volume"]
    if has_volume:
        header.append("volume")
    if has_spread:
        header.append("spread")

    format_price = (lambda value: value) if decimals is None else (lambda value: f"{value:.{decimals}f}")

    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="") as out:
        # "\n", not csv's default "\r\n", so this and `write_frame` agree byte for byte.
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(header)

        for record in records:
            row = [
                record.dt.strftime(DATE_FORMAT),
                record.dt.strftime(TIME_FORMAT),
                format_price(record.open),
                format_price(record.high),
                format_price(record.low),
                format_price(record.close),
                _blank_if_none(record.tick_volume),
            ]

            if has_volume:
                row.append(_blank_if_none(record.volume))

            if has_spread:
                row.append(_blank_if_none(record.spread))

            writer.writerow(row)


def _blank_if_none(value: int | None) -> int | str:
    return "" if value is None else value


def _parse_datetime(date_text: str, time_text: str) -> datetime:
    stamp = f"{date_text.strip()} {time_text.strip()}"

    for fmt in DATETIME_FORMATS:
        try:
            return datetime.strptime(stamp, fmt)
        except ValueError:
            continue

    raise ValueError(f"unrecognized timestamp {stamp!r}")


def _to_count(text: str) -> int | None:
    """A volume or spread: None when blank; `10.0` (some exports write floats) is 10."""
    text = text.strip()

    if not text:
        return None

    return int(float(text))


def parse_fields(fields: list[str], columns: dict[str, int]) -> MetatraderRecord:
    """One line's fields as a record; ValueError, with the reason, when they don't parse."""
    def field(name: str) -> str:
        index = columns.get(name)

        if index is None or index >= len(fields):
            return ""

        return fields[index]

    missing = [name for name in REQUIRED_FIELDS if not field(name)]

    if missing:
        raise ValueError(f"missing field(s): {', '.join(missing)}")

    return MetatraderRecord(
        dt=_parse_datetime(field("date"), field("time")),
        open=float(field("open")),
        high=float(field("high")),
        low=float(field("low")),
        close=float(field("close")),
        tick_volume=_to_count(field("tick_volume")),
        volume=_to_count(field("volume")),
        spread=_to_count(field("spread")),
    )
