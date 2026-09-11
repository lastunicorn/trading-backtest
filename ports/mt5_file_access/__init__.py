"""Readers that turn raw MT5 export files into typed objects.

`mt5_bar_reader` stops at parsing: one `Bar` per record (the `domain.bar.Bar`
entity), nothing cleaned, deduplicated or resampled; its own code is stdlib
only. `mt5_frame_reader` builds on it with pandas, turning an export straight
into a DataFrame -- still parsing only, no cross-file dedup, which stays a
`domain/` decision.

Re-exported so callers can use the short form (`Bar` for convenience; its
canonical home is `domain.bar`):

    from ports.mt5_file_access import read_bars, iter_bars, Bar, read_frame, write_frame
"""

from ports.mt5_file_access.mt5_frame_reader import read_frame, write_frame
from ports.mt5_file_access.mt5_bar_reader import (
    Bar,
    BarParseError,
    SourceLayout,
    detect_layout,
    iterate_bars,
    read_bars,
    sniff_layout,
)

__all__ = [
    "Bar",
    "BarParseError",
    "SourceLayout",
    "detect_layout",
    "iterate_bars",
    "read_bars",
    "read_frame",
    "sniff_layout",
    "write_frame",
]
