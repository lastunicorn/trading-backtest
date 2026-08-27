"""Readers that turn raw market-data files into typed objects.

The port stops at parsing: one `Bar` per record, nothing cleaned, deduplicated
or resampled. Everything downstream of that is `domain/`.

Re-exported so callers can use the short form:

    from ports.mt5_file_access import read_bars, iter_bars, Bar
"""

from ports.mt5_file_access.mt5_reader import (
    Bar,
    BarParseError,
    detect_layout,
    iter_bars,
    read_bars,
)

__all__ = ["Bar", "BarParseError", "detect_layout", "iter_bars", "read_bars"]
