"""Read and write MetaTrader (MT4/MT5) bar exports: CSVs of date, time, OHLC and optional volumes and spread.

Two ways in, with the same parsing rules:

    from libs.metatrader_csv import iterate_records, read_frame

    for record in iterate_records(path): ...   # MetatraderRecord per line, stdlib only, streaming
    frame = read_frame(path)                   # one DataFrame, pandas, fast

Values come back as the file holds them: a blank or absent volume or spread
is None/NA, timestamps are naive. See README.md.

Self-contained: depends on pandas only, never on the rest of this repo.
"""

from .errors import AmbiguousLayoutError, MetatraderParseError
from .export_layout import FIELDS, HEADERLESS_LAYOUTS, REQUIRED_FIELDS, Layout, sniff_layout
from .frames import read_frame, write_frame
from .records import MetatraderRecord, iterate_records, read_records, write_records

__all__ = [
    "FIELDS",
    "HEADERLESS_LAYOUTS",
    "REQUIRED_FIELDS",
    "AmbiguousLayoutError",
    "Layout",
    "MetatraderParseError",
    "MetatraderRecord",
    "iterate_records",
    "read_frame",
    "read_records",
    "sniff_layout",
    "write_frame",
    "write_records",
]
