"""Shift a frame's `datetime` column from one timezone's wall clock to another.

The pandas counterpart to `domain.bar_approach.shift_bars`, vectorised instead
of bar-by-bar. `datetime` is naive (no tzinfo), as everywhere else in this
codebase. It is treated as a wall-clock reading already in `from_tz`,
converted to `to_tz`, then returned naive again so the result stays
consistent with the rest of the codebase.

    from zoneinfo import ZoneInfo
    from domain.pandas_approach.shift_timezone import shift_timezone

    utc = shift_timezone(frame, ZoneInfo("UTC"))   # from_tz defaults to broker server time

`from_tz` defaults to `BROKER_SERVER_TZ` -- New York + 7h, see
`domain.broker_clock` -- the only source this codebase has ever shifted from,
but stays a parameter so a caller with a different source is not blocked.

pandas only accepts IANA/fixed-offset zones, not a custom `tzinfo` like
`ShiftedZone`, so a shifted clock is converted through its base zone: take off
the shift, then localize in the base zone (and the reverse on the way out).

`BROKER_SERVER_TZ` is re-exported here for existing callers; its home is
`domain.broker_clock`.
"""

from __future__ import annotations

from datetime import timedelta, tzinfo

import pandas as pd

from domain.broker_clock import BROKER_SERVER_TZ, ShiftedZone

__all__ = ["BROKER_SERVER_TZ", "shift_timezone"]


def shift_timezone(frame: pd.DataFrame, to_tz: tzinfo, *, from_tz: tzinfo = BROKER_SERVER_TZ) -> pd.DataFrame:
    """Return `frame` with `datetime` re-expressed in `to_tz`, still naive.

    `frame["datetime"]` is assumed naive, holding a wall-clock time in
    `from_tz`. Every other column passes through unchanged.
    """
    from_base, from_shift = _pandas_zone(from_tz)
    to_base, to_shift = _pandas_zone(to_tz)

    instants = (frame["datetime"] - from_shift).dt.tz_localize(from_base)
    stamps = instants.dt.tz_convert(to_base).dt.tz_localize(None) + to_shift
    return frame.assign(datetime=stamps)


def _pandas_zone(tz: tzinfo) -> tuple[tzinfo, timedelta]:
    """A zone pandas accepts, plus the wall-clock shift to apply on top of it."""
    if isinstance(tz, ShiftedZone):
        return tz.base, tz.shift
    return tz, timedelta(0)
