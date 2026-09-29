"""Synthetic days for the `strategies.session_breakout` tests.

M5 bars on the UTC clock unless a test shifts them. The default session
(00:00-09:00 UTC) bars span 1.0995-1.1005: H 1.1005, L 1.0995, a 10-pip
range, midpoint 1.1000. Every other bar stays strictly inside that
(1.0997-1.1003): touching a level counts as a break. Tests override the bars
they care about by time of day.
"""

from datetime import UTC, date

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

TUESDAY = date(2026, 1, 6)
WEDNESDAY = date(2026, 1, 7)

SESSION = (1.1000, 1.1005, 1.0995, 1.1000)
QUIET = (1.1000, 1.1003, 1.0997, 1.1000)
FLAT = (1.1000, 1.1000, 1.1000, 1.1000)

BREAK_UP = (1.1003, 1.1008, 1.1002, 1.1007)
BREAK_DOWN = (1.0997, 1.0998, 1.0992, 1.0993)
BOTH_WAYS = (1.1000, 1.1008, 1.0992, 1.1000)


def day_frame(day: date = TUESDAY, overrides: dict[str, tuple] | None = None,
              session: tuple = SESSION, drop_before: str | None = None) -> pd.DataFrame:
    """M5 bars for all of `day`: `session` bars 00:00-09:00, quiet after, except `overrides` ("HH:MM" -> bar).

    `drop_before` leaves out every bar earlier than that "HH:MM".
    """
    overrides = overrides or {}
    rows = []
    for stamp in pd.date_range(pd.Timestamp(day), periods=288, freq="5min"):
        key = stamp.strftime("%H:%M")
        if drop_before is not None and key < drop_before:
            continue
        default = session if key < "09:00" else QUIET
        rows.append((stamp, *overrides.get(key, default)))
    return pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close"])


def data(*frames: pd.DataFrame, **kwargs) -> HistoricalData:
    frame = pd.concat(frames or [day_frame()], ignore_index=True)
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd(), timezone=kwargs.pop("timezone", UTC), **kwargs)
