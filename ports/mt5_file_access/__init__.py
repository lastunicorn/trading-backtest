"""MT5 export files as the repo's `Bar`s and bar frames.

The format itself (separators, headers, column layouts, timestamps) is
`libs.metatrader_csv`. This port turns what it reads into this application's
shapes: `mt5_bar_reader` into `Bar` objects (the `domain.bar_approach.bar.Bar`
entity), `mt5_frame_reader` into a DataFrame. Parsing only -- nothing cleaned,
deduplicated or resampled, which stays a `domain/` decision.

Re-exported so callers can use the short form (`Bar` for convenience; its
canonical home is `domain.bar_approach.bar`):

    from ports.mt5_file_access import read_bars, iterate_bars, Bar, read_frame, write_frame
"""

from ports.mt5_file_access.mt5_bar_reader import Bar, BarParseError, iterate_bars, read_bars
from ports.mt5_file_access.mt5_frame_reader import read_frame, write_frame

__all__ = [
    "Bar",
    "BarParseError",
    "iterate_bars",
    "read_bars",
    "read_frame",
    "write_frame",
]
