"""Shift a frame's `datetime` column from one timezone's wall clock to another.

The pandas counterpart to `domain.bar_approach.shift_bars`, vectorised instead
of bar-by-bar. `datetime` is naive (no tzinfo), as everywhere else in this
codebase. It is treated as a wall-clock reading already in `from_tz`,
localized, converted to `to_tz`, then returned naive again so the result stays
consistent with the rest of the codebase.

    from zoneinfo import ZoneInfo
    from domain.pandas_approach.shift_timezone import shift_timezone

    utc = shift_timezone(frame, ZoneInfo("UTC"))   # from_tz defaults to broker server time

`from_tz` defaults to `America/New_York` -- broker server time, the only
source this codebase has ever shifted from -- but stays a parameter rather
than a hardcoded constant, so a caller with a different source is not blocked.
"""

from __future__ import annotations

from datetime import tzinfo
from zoneinfo import ZoneInfo

import pandas as pd

__all__ = ["shift_timezone"]

_BROKER_SERVER_TZ = ZoneInfo("America/New_York")


def shift_timezone(frame: pd.DataFrame, to_tz: tzinfo, *, from_tz: tzinfo = _BROKER_SERVER_TZ) -> pd.DataFrame:
    """Return `frame` with `datetime` re-expressed in `to_tz`, still naive.

    `frame["datetime"]` is assumed naive, holding a wall-clock time in
    `from_tz`. Every other column passes through unchanged.
    """
    stamps = frame["datetime"].dt.tz_localize(from_tz).dt.tz_convert(to_tz).dt.tz_localize(None)
    return frame.assign(datetime=stamps)
