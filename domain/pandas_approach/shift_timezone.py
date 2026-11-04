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
the shift, then localize in the base zone (and the reverse on the way out). A
`SwitchingZone` converts each row through `before` or `after`, whichever holds
at that row.

`BROKER_SERVER_TZ` is re-exported here for existing callers; its home is
`domain.broker_clock`.
"""

from __future__ import annotations

from datetime import UTC, tzinfo

import numpy as np
import pandas as pd

from domain.broker_clock import BROKER_SERVER_TZ, ShiftedZone, SwitchingZone

__all__ = ["BROKER_SERVER_TZ", "shift_timezone"]


def shift_timezone(frame: pd.DataFrame, to_tz: tzinfo, *, from_tz: tzinfo = BROKER_SERVER_TZ) -> pd.DataFrame:
    """Return `frame` with `datetime` re-expressed in `to_tz`, still naive.

    `frame["datetime"]` is assumed naive, holding a wall-clock time in
    `from_tz`. Every other column passes through unchanged.
    """
    return frame.assign(datetime=_from_utc(_to_utc(frame["datetime"], from_tz), to_tz))


def _to_utc(wall: pd.Series, tz: tzinfo) -> pd.Series:
    """Naive wall-clock readings in `tz` -> tz-aware UTC instants."""
    if isinstance(tz, SwitchingZone):
        before = (wall < pd.Timestamp(tz.switch)).to_numpy()
        # Each side is localized on its own rows only: a reading that doesn't
        # exist in the other zone (a DST gap) must not raise.
        return _combine(before, _to_utc(wall[before], tz.before), _to_utc(wall[~before], tz.after))
    if isinstance(tz, ShiftedZone):
        return _to_utc(wall - tz.shift, tz.base)
    return wall.dt.tz_localize(tz).dt.tz_convert(UTC)


def _from_utc(instants: pd.Series, tz: tzinfo) -> pd.Series:
    """Tz-aware instants -> naive wall-clock readings in `tz`."""
    if isinstance(tz, SwitchingZone):
        switch = tz.switch.replace(tzinfo=tz.after).astimezone(UTC)
        before = (instants < pd.Timestamp(switch)).to_numpy()
        return _combine(before, _from_utc(instants[before], tz.before), _from_utc(instants[~before], tz.after))
    if isinstance(tz, ShiftedZone):
        return _from_utc(instants, tz.base) + tz.shift
    return instants.dt.tz_convert(tz).dt.tz_localize(None)


def _combine(take_first: np.ndarray, first: pd.Series, second: pd.Series) -> pd.Series:
    """`first`'s rows where `take_first`, `second`'s elsewhere, back in the original row order."""
    positions = np.concatenate([np.flatnonzero(take_first), np.flatnonzero(~take_first)])
    return pd.concat([first, second]).iloc[np.argsort(positions, kind="stable")]
