"""Reader for raw MT5 CSV exports.

Parses an export into `Bar` objects (the domain entity, `domain.bar.Bar`) so
callers never re-implement timestamp/price parsing. Pure I/O: no cleaning, no
resampling, no strategy logic. This module's own code is stdlib only -- its one
non-stdlib dependency is the pandas-free `domain.bar`.

    from ports.mt5_file_access import read_bars, iter_bars

    bars = read_bars("data/eurusd/1min/EURUSD_2020_01.csv")   # list[Bar]
    print(bars[0].dt, bars[0].close)

    for bar in iter_bars(path):        # streaming, constant memory
        ...

Handles both export shapes seen in this repo:

  * headerless   2020.01.02,00:00,1.12112,1.12112,1.12098,1.12098,10
  * MT5 headers  <DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>...

Separator (comma, tab or semicolon) is detected per file.
"""

from __future__ import annotations

import csv
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime

from domain.bar_approach.bar import Bar

__all__ = [
    "Bar",  # re-exported for convenience; canonical import is `from domain.bar import Bar`
    "BarParseError",
    "SourceLayout",
    "detect_layout",
    "iterate_bars",
    "read_bars",
    "sniff_layout",
]

DELIMITERS = (",", "\t", ";")

# Exports under data/eurusd/ mostly use `2020.01.02,00:00`, but MT5 can also
# export with seconds (`2026.07.01\t00:00:00`) -- both are tried in order.
# A file in any other layout fails the parse -- skipped when strict=False,
# raised otherwise -- rather than being silently reinterpreted.
DATETIME_FORMAT = "%Y.%m.%d %H:%M"
DATETIME_FORMAT_WITH_SECONDS = "%Y.%m.%d %H:%M:%S"

# Canonical field name -> the header spellings that map onto it.
HEADER_ALIASES = {
    "date": ("date",),
    "time": ("time",),
    "open": ("open", "o"),
    "high": ("high", "h"),
    "low": ("low", "l"),
    "close": ("close", "c"),
    "tick_volume": ("tickvol", "tickvolume", "tick_volume"),
    "real_volume": ("vol", "volume", "realvolume", "real_volume"),
    "spread": ("spread",),
}

# Positional layouts for headerless exports, keyed by column count. MT5's full
# M1 export is DATE TIME OHLC TICKVOL VOL SPREAD; brokers drop the tail fields.
# The 8-column case is ambiguous (VOL or SPREAD?) -- treated as SPREAD, which
# is what the exports in data/eurusd/ use.
POSITIONAL_LAYOUTS = {
    6: ("date", "time", "open", "high", "low", "close"),
    7: ("date", "time", "open", "high", "low", "close", "tick_volume"),
    8: ("date", "time", "open", "high", "low", "close", "tick_volume", "spread"),
    9: ("date", "time", "open", "high", "low", "close", "tick_volume", "real_volume", "spread"),
}

REQUIRED_FIELDS = ("date", "time", "open", "high", "low", "close")


class BarParseError(ValueError):
    """A line could not be turned into a Bar."""

    def __init__(self, path: str, line_no: int, reason: str, line: str = ""):
        self.path = path
        self.line_no = line_no
        self.reason = reason
        self.line = line

        location = f"{os.path.basename(path)}:{line_no}"
        detail = f"  |  {line.strip()[:80]}" if line else ""
        super().__init__(f"{location}: {reason}{detail}")


@dataclass(frozen=True, slots=True)
class SourceLayout:
    """What an export's first row reveals, without parsing the rest.

    `columns` maps canonical field name -> column index (exactly the old
    `detect_layout` return). `has_header` says whether the first row is a header
    a reader must not treat as data; `field_count` is how many columns that row
    split into. Enough for a bulk reader (`mt5_frame_reader.read_frame`) to hand
    the file straight to a parser without sniffing it a second time.
    """

    delimiter: str
    columns: dict[str, int]
    has_header: bool
    field_count: int


def _detect_delimiter(sample: str) -> str:
    """Pick the delimiter that splits the sample line into the most fields."""
    best = ","
    best_count = 0

    for delimiter in DELIMITERS:
        count = sample.count(delimiter)

        if count > best_count:
            best = delimiter
            best_count = count

    return best


def _normalize_header(field: str) -> str:
    return field.strip().strip("<>").replace(" ", "").lower()


def _looks_like_header(fields: list[str]) -> bool:
    """True for '<DATE>,<TIME>,...' and other non-numeric first lines."""
    if not fields:
        return False

    first = fields[0].strip()
    return first.startswith("<") or _normalize_header(first) in ("date", "datetime")


def _layout_from_header(fields: list[str]) -> dict[str, int]:
    layout: dict[str, int] = {}

    for index, raw in enumerate(fields):
        name = _normalize_header(raw)

        for canonical, aliases in HEADER_ALIASES.items():
            if name in aliases and canonical not in layout:
                layout[canonical] = index
                break

    return layout


def _positional_layout(n_fields: int) -> dict[str, int]:
    """Best-guess layout for a headerless row of n_fields columns."""
    names = POSITIONAL_LAYOUTS.get(n_fields)

    if names is None:
        # Unknown width: map what we can positionally and ignore the rest.
        names = POSITIONAL_LAYOUTS[9][:n_fields] if n_fields < 9 else POSITIONAL_LAYOUTS[9]

    return {name: index for index, name in enumerate(names)}


def _layout_for_row(fields: list[str]) -> tuple[dict[str, int], bool]:
    """Layout implied by the file's first non-empty row.

    Returns (layout, row_is_header) so the caller knows whether that row still
    has to be consumed as data.
    """
    if _looks_like_header(fields):
        layout = _layout_from_header(fields)

        # Header present but unusable -- fall back to positions.
        if not all(name in layout for name in REQUIRED_FIELDS):
            layout = _positional_layout(len(fields))

        return layout, True

    return _positional_layout(len(fields)), False


def sniff_layout(path: str) -> SourceLayout | None:
    """Inspect the first non-empty row of `path`; None for an empty file.

    One cheap read decides everything a bulk parser needs: the delimiter,
    whether row 1 is a header, and which column each field sits in. `detect_layout`
    is this with only the column map kept.
    """
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()

        if not first_line:
            return None

        delimiter = _detect_delimiter(first_line)
        handle.seek(0)

        for fields in csv.reader(handle, delimiter=delimiter):
            if not fields or not any(field.strip() for field in fields):
                continue

            layout, row_is_header = _layout_for_row(fields)
            return SourceLayout(delimiter, layout, row_is_header, len(fields))

    return None


def detect_layout(path: str) -> dict[str, int]:
    """Map field name -> column index for `path`, without parsing any bars.

    Tells a caller which fields the export actually carries: a 7-column MT5 M1
    file yields date/time/OHLC/tick_volume and no spread or real_volume. Returns
    an empty dict for an empty file.
    """
    found = sniff_layout(path)
    return found.columns if found is not None else {}


def _parse_datetime(date_text: str, time_text: str) -> datetime:
    stamp = f"{date_text.strip()} {time_text.strip()}"

    for fmt in (DATETIME_FORMAT, DATETIME_FORMAT_WITH_SECONDS):
        try:
            return datetime.strptime(stamp, fmt)
        except ValueError:
            continue

    raise ValueError(f"unrecognized timestamp {stamp!r}")


def _to_int(text: str) -> int:
    text = text.strip()

    if not text:
        return 0

    # Some exports write volumes as floats ("10.0").
    return int(float(text))


def _build_bar(fields: list[str], layout: dict[str, int]) -> Bar:
    def field(name: str) -> str:
        index = layout.get(name)

        if index is None or index >= len(fields):
            return ""

        return fields[index]

    missing = [name for name in REQUIRED_FIELDS if not field(name)]

    if missing:
        raise ValueError(f"missing field(s): {', '.join(missing)}")

    spread_text = field("spread").strip()

    return Bar(
        dt=_parse_datetime(field("date"), field("time")),
        open=float(field("open")),
        high=float(field("high")),
        low=float(field("low")),
        close=float(field("close")),
        tick_volume=_to_int(field("tick_volume")),
        real_volume=_to_int(field("real_volume")),
        spread=_to_int(spread_text) if spread_text else None,
    )


def iterate_bars(
    path: str,
    *,
    strict: bool = True,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> Iterator[Bar]:
    """Yield each Bar in `path`, one at a time.

    Memory stays flat regardless of file size, so this is the one to use on the
    multi-million-row combined exports.

    strict   -- True raises BarParseError on a malformed line; False skips it.
    on_skip  -- called as (line_no, line, reason) for each skipped line.
    """
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()

        if not first_line:
            return

        delimiter = _detect_delimiter(first_line)
        handle.seek(0)

        layout: dict[str, int] | None = None

        for line_no, fields in enumerate(csv.reader(handle, delimiter=delimiter), 1):
            if not fields or not any(field.strip() for field in fields):
                continue

            if layout is None:
                layout, row_is_header = _layout_for_row(fields)

                if row_is_header:
                    continue  # never treat the header row as data

            try:
                yield _build_bar(fields, layout)
            except ValueError as exc:
                if strict:
                    raise BarParseError(
                        path, line_no, str(exc), delimiter.join(fields)
                    ) from exc

                if on_skip is not None:
                    on_skip(line_no, delimiter.join(fields), str(exc))


def read_bars(
    path: str,
    *,
    strict: bool = True,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> list[Bar]:
    """Read `path` fully into a list of Bars, in file order.

    Convenient for a single monthly export (~31k bars). Prefer iter_bars() when
    the file could be large.
    """
    return list(iterate_bars(path, strict=strict, on_skip=on_skip))
