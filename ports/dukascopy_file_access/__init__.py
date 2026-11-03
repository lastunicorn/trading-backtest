"""Reads Dukascopy M1 bid/ask export pairs into one DataFrame of bars.

The files themselves are found, paired and read by `libs.dukascopy_csv`; this
port turns each pair into the repo's bar-frame shape (OHLC from bid, spread
derived from ask - bid).

Re-exported so callers can use the short form:

    from ports.dukascopy_file_access import read_path

    read_path(folder)     # every pair under a folder (or the pair one file belongs to)
"""

from ports.dukascopy_file_access.dukascopy_frame_reader import FRAME_COLUMNS, read_path

__all__ = ["FRAME_COLUMNS", "read_path"]
