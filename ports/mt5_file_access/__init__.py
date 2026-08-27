"""Readers that turn raw market-data files into typed objects.

`mt5_reader` stops at parsing: one `Bar` per record, nothing cleaned,
deduplicated or resampled, stdlib only. `mt5_frame_reader` builds on it with
pandas, turning an export straight into a DataFrame -- still parsing only, no
cross-file dedup, which stays a `domain/` decision.

Re-exported so callers can use the short form:

    from ports.mt5_file_access import read_bars, iter_bars, Bar, read_frame, write_frame
"""

from ports.mt5_file_access.mt5_frame_reader import read_frame, write_frame
from ports.mt5_file_access.mt5_bar_reader import (
    Bar,
    BarParseError,
    detect_layout,
    iter_bars,
    read_bars,
)

__all__ = [
    "Bar",
    "BarParseError",
    "detect_layout",
    "iter_bars",
    "read_bars",
    "read_frame",
    "write_frame",
]
