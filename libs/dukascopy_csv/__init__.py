"""Find and read Dukascopy candle exports (the CSVs dukascopy-node downloads).

Each export holds one price side (bid or ask) of one instrument over one
period. This library hands back each file on its own; combining a bid file
with its ask file is the caller's business. See README.md.

    from libs.dukascopy_csv import find_files, pair_files, read_file

    for pair in pair_files(find_files("/data/dukascopy/eurusd")):
        bid, ask = read_file(pair.bid), read_file(pair.ask)

Self-contained: depends on pandas only, never on the rest of this repo.
"""

from .dukascopy_file import DukascopyFile, DukascopyFilePair, PriceSide
from .dukascopy_reader import REQUIRED_COLUMNS, DukascopyFormatError, read_file
from .file_discovery import find_files, find_pair, pair_files

__all__ = [
    "REQUIRED_COLUMNS",
    "DukascopyFile",
    "DukascopyFilePair",
    "DukascopyFormatError",
    "PriceSide",
    "find_files",
    "find_pair",
    "pair_files",
    "read_file",
]
