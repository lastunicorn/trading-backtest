"""Reads Dukascopy EURUSD M1 bid/ask export pairs into a DataFrame.

A Dukascopy export is one file per side per month
(`eurusd-m1-bid-2020-01-01-2020-02-01.csv` / `eurusd-m1-ask-...`), so this
port -- unlike `mt5_file_access` -- necessarily reads two files together to
produce one record shape (OHLC from bid, spread derived from ask - bid).

Re-exported so callers can use the short form:

    from ports.ducascopy import read_frame

    read_frame(2020)      # whole year
    read_frame(2020, 3)   # March 2020 only
    read_path(folder)     # every pair under a folder (or the pair one file belongs to)

The export folder's location is machine-specific and lives in
`ports/ducascopy/config.py` (gitignored) -- see `config.example.py`.
"""

from ports.ducascopy.ducascopy_frame_reader import FRAME_COLUMNS, read_frame, read_path

__all__ = ["FRAME_COLUMNS", "read_frame", "read_path"]
