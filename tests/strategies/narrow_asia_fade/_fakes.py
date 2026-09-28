"""Synthetic days for the `strategies.narrow_asia_fade` tests.

Default bars have tick volume 10. Asia's (02:00-10:00) span 1.0995-1.1005, so
the Asia range is 10 pips (H 1.1005, L 1.0995, midpoint 1.1000). Every other
bar stays strictly inside that (1.0997-1.1003): touching a level counts as a
break, so a bar *at* H or L would already be one. Tests override the bars they
care about by time of day.
"""

from datetime import date

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

MONDAY = date(2026, 1, 5)
ASIA = (1.1000, 1.1005, 1.0995, 1.1000, 10)
QUIET = (1.1000, 1.1003, 1.0997, 1.1000, 10)

# An upside break with enough volume, and a bar trading back below H.
BREAK_UP = (1.1004, 1.1008, 1.1003, 1.1007, 30)
BACK_BELOW_H = (1.1006, 1.1006, 1.1002, 1.1003, 10)
# Holding above H after the break, so no re-entry yet.
ABOVE_H = (1.1007, 1.1009, 1.1006, 1.1008, 10)
# The downside mirror.
BREAK_DOWN = (1.0996, 1.0997, 1.0992, 1.0993, 30)
BACK_ABOVE_L = (1.0994, 1.0998, 1.0994, 1.0997, 10)
BELOW_L = (1.0993, 1.0994, 1.0991, 1.0992, 10)


def day_frame(day: date = MONDAY, overrides: dict[str, tuple] | None = None,
              drop: list[str] | None = None) -> pd.DataFrame:
    """M5 bars for all of `day`: quiet, except `overrides` ("HH:MM" -> bar), minus `drop` times."""
    overrides = overrides or {}
    drop = set(drop or [])
    rows = []
    for stamp in pd.date_range(pd.Timestamp(day), periods=288, freq="5min"):
        key = stamp.strftime("%H:%M")
        if key in drop:
            continue
        default = ASIA if "02:00" <= key < "10:00" else QUIET
        rows.append((stamp, *overrides.get(key, default)))
    frame = pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close", "tick_volume"])
    frame["tick_volume"] = frame["tick_volume"].astype("Int64")
    return frame


def data(*frames: pd.DataFrame, **kwargs) -> HistoricalData:
    frame = pd.concat(frames or [day_frame()], ignore_index=True)
    return HistoricalData(frame, kwargs.pop("timeframe", SampleSize.Parse("5m")), EurUsd(), **kwargs)
