"""The shape of a MetaTrader (MT4/MT5) bar export: separator, header, which column holds which field.

Two shapes occur:

  * MT5 headers  <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>
  * headerless   2020.01.02,00:00,1.12112,1.12112,1.12098,1.12098,10

The separator (comma, tab or semicolon) is detected per file. A header names
its columns; a headerless file is mapped by its column count, using MetaTrader's
full column order DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD with the tail
dropped. Eight columns is ambiguous -- TICKVOL VOL or TICKVOL SPREAD -- so the
caller has to say which (`headerless_layouts`).

The fields, under the names this library uses everywhere: date, time, open,
high, low, close, tick_volume, volume (MetaTrader's real volume, <VOL>), spread
(in points).
"""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .errors import AmbiguousLayoutError

__all__ = [
    "DATETIME_FORMATS",
    "DATE_FORMAT",
    "DELIMITERS",
    "FIELDS",
    "HEADERLESS_LAYOUTS",
    "REQUIRED_FIELDS",
    "TIME_FORMAT",
    "Layout",
    "sniff_layout",
]

DELIMITERS = (",", "\t", ";")

# A timestamp is a date and a time column: `2020.01.02,00:00`, or with seconds
# (`2026.07.01\t00:00:00`). Both are tried, in this order.
DATE_FORMAT = "%Y.%m.%d"
TIME_FORMAT = "%H:%M"
DATETIME_FORMATS = (f"{DATE_FORMAT} {TIME_FORMAT}", f"{DATE_FORMAT} {TIME_FORMAT}:%S")

FIELDS = ("date", "time", "open", "high", "low", "close", "tick_volume", "volume", "spread")
REQUIRED_FIELDS = ("date", "time", "open", "high", "low", "close")

# Field name -> the header spellings that map onto it (after dropping `<>`,
# spaces and case).
HEADER_ALIASES = {
    "date": ("date",),
    "time": ("time",),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
    "tick_volume": ("tickvol", "tickvolume", "tick_volume"),
    "volume": ("vol", "volume", "realvolume", "real_volume"),
    "spread": ("spread",),
}

# Headerless layouts by column count: MetaTrader's full order with the tail
# fields dropped. 8 columns is missing on purpose: see `AMBIGUOUS_WIDTHS`.
HEADERLESS_LAYOUTS: Mapping[int, tuple[str, ...]] = {
    6: FIELDS[:6],
    7: FIELDS[:7],
    9: FIELDS,
}

# Column counts that fit more than one layout: 8 is TICKVOL+VOL or TICKVOL+SPREAD.
AMBIGUOUS_WIDTHS = frozenset({8})


@dataclass(frozen=True, slots=True)
class Layout:
    """What an export's first non-empty row reveals, without parsing the rest.

    `columns` maps field name -> column index, for the fields the export
    carries. `has_header` says whether that first row is a header rather than
    data; `field_count` is how many columns it split into; `first_row` is its
    line number (after any leading blank lines).
    """

    delimiter: str
    columns: dict[str, int]
    has_header: bool
    field_count: int
    first_row: int = 1

    @property
    def has_required_fields(self) -> bool:
        """Whether every row can place a date, a time and the four prices."""
        return all(name in self.columns for name in REQUIRED_FIELDS)


def sniff_layout(path: str, *, headerless_layouts: Mapping[int, Sequence[str]] | None = None) -> Layout | None:
    """The layout of the export at `path`, from its first non-empty row; None for an empty file.

    `headerless_layouts` adds to or overrides `HEADERLESS_LAYOUTS` by column
    count, e.g. `{8: (*FIELDS[:7], "spread")}` for exports whose eighth column
    is the spread. Raises AmbiguousLayoutError for a headerless 8-column file
    without one.
    """
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()

        if not first_line:
            return None

        delimiter = detect_delimiter(first_line)
        handle.seek(0)

        for line_no, fields in enumerate(csv.reader(handle, delimiter=delimiter), 1):
            if is_blank(fields):
                continue

            columns, row_is_header = layout_of_row(fields, headerless_layouts, path)
            return Layout(delimiter, columns, row_is_header, len(fields), first_row=line_no)

    return None


def detect_delimiter(sample: str) -> str:
    """The delimiter that splits `sample` (a line) into the most fields; comma on a tie."""
    best = ","
    best_count = 0

    for delimiter in DELIMITERS:
        count = sample.count(delimiter)

        if count > best_count:
            best = delimiter
            best_count = count

    return best


def is_blank(fields: list[str]) -> bool:
    return not fields or not any(field.strip() for field in fields)


def layout_of_row(
    fields: list[str], headerless_layouts: Mapping[int, Sequence[str]] | None, path: str
) -> tuple[dict[str, int], bool]:
    """The column map implied by a file's first non-empty row, and whether that row is a header.

    A header that doesn't name a date, time and the four prices is treated as
    unusable and the columns fall back to positions.
    """
    if _looks_like_header(fields):
        columns = _columns_from_header(fields)

        if not all(name in columns for name in REQUIRED_FIELDS):
            columns = _positional_columns(len(fields), headerless_layouts, path)

        return columns, True

    return _positional_columns(len(fields), headerless_layouts, path), False


def _normalize_header(field: str) -> str:
    return field.strip().strip("<>").replace(" ", "").lower()


def _looks_like_header(fields: list[str]) -> bool:
    """True for '<DATE>,<TIME>,...' and other first rows that start with a date/datetime label."""
    if not fields:
        return False

    first = fields[0].strip()
    return first.startswith("<") or _normalize_header(first) in ("date", "datetime")


def _columns_from_header(fields: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}

    for index, raw in enumerate(fields):
        name = _normalize_header(raw)

        for field, aliases in HEADER_ALIASES.items():
            if name in aliases and field not in columns:
                columns[field] = index
                break

    return columns


def _positional_columns(
    field_count: int, headerless_layouts: Mapping[int, Sequence[str]] | None, path: str
) -> dict[str, int]:
    """The column map for a headerless row of `field_count` columns."""
    layouts = {**HEADERLESS_LAYOUTS, **(headerless_layouts or {})}
    names = layouts.get(field_count)

    if names is None:
        if field_count in AMBIGUOUS_WIDTHS:
            raise AmbiguousLayoutError(
                f"{path}: a headerless {field_count}-column export is ambiguous (TICKVOL VOL or "
                f"TICKVOL SPREAD); pass headerless_layouts={{{field_count}: (...)}} to say which"
            )
        # Any other width: map what fits MetaTrader's order, ignore the rest.
        names = FIELDS[:field_count]

    return {name: index for index, name in enumerate(names)}
