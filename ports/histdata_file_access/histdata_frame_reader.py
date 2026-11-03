"""histdata.com MetaTrader downloads (`DAT_MT_<SYMBOL>_M1_<YYYYMM>.csv`) as the repo's bar frames.

The files are plain headerless MetaTrader exports, so the format itself is
`libs.metatrader_csv`. What this port adds is what is true of histdata's
files in particular:

  * the seventh column is a volume histdata always leaves at 0, so it is
    dropped rather than handed on as zeros that look like data;
  * there is no spread column;
  * the timestamps are New York time (`TIMEZONE`): the week opens Sunday
    17:00 in winter and summer alike;
  * each csv sits beside a `.txt` gap report, which `FILE_PATTERN` leaves out.

Parsing only -- no sorting, no dedup; that stays a `domain/` decision.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd

from libs import metatrader_csv

__all__ = ["FILE_PATTERN", "FRAME_COLUMNS", "TIMEZONE", "read_frame"]

# The csv files of a histdata MetaTrader download, without the gap reports beside them.
FILE_PATTERN = "DAT_MT_*.csv"

# The clock of the timestamps, as an IANA name.
TIMEZONE = "America/New_York"

FRAME_COLUMNS = ("open", "high", "low", "close")


def read_frame(
    path: str | Path,
    *,
    strict: bool = True,
    on_skip: Callable[[int, str, str], None] | None = None,
) -> pd.DataFrame:
    """Read one histdata MetaTrader download into a DataFrame, in file order.

    Columns: `datetime` (naive, New York time), then open/high/low/close as
    float64. An empty file gives a frame with those columns and no rows.

    strict   -- True raises `libs.metatrader_csv.MetatraderParseError` on a malformed line; False drops it.
    on_skip  -- called as (line_no, line, reason) for each dropped line.
    """
    frame = metatrader_csv.read_frame(path, strict=strict, on_skip=on_skip)
    return frame[["datetime", *FRAME_COLUMNS]]
