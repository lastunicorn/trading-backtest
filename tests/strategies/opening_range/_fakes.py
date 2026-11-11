"""Synthetic days for the `strategies.opening_range` tests and the ORB strategies built on it.

Bars are built on New York's wall clock, keyed "HH:MM" ET, then relabelled to
the clock a test asks for (UTC by default). The opening-range bars (09:30-09:45)
span 1.0995-1.1005: H 1.1005, L 1.0995, a 10-pip range, midpoint 1.1000. Every
other bar stays strictly inside that (1.0997-1.1003): touching a level counts
as a break.
"""

from dataclasses import dataclass
from datetime import UTC, date
from zoneinfo import ZoneInfo

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.backtesting.position import Position
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.sample_size import SampleSize
from domain.symbol import EURUSD
from strategies.opening_range import OpeningRangeStrategy

NEW_YORK = ZoneInfo("America/New_York")

TUESDAY = date(2026, 1, 6)       # EST: 09:30 ET is 14:30 UTC
WEDNESDAY = date(2026, 1, 7)
SUMMER_TUESDAY = date(2026, 7, 7)   # EDT: 09:30 ET is 13:30 UTC
MISMATCH_TUESDAY = date(2026, 3, 10)   # New York on EDT, London still on GMT: 08:00 London is 04:00 ET

RANGE = (1.1000, 1.1005, 1.0995, 1.1000)
QUIET = (1.1000, 1.1003, 1.0997, 1.1000)
FLAT = (1.1000, 1.1000, 1.1000, 1.1000)


@dataclass(frozen=True)
class RangeOnly(OpeningRangeStrategy):
    """The base class alone: a range and its windows, no entries."""

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        return []


def day_frame(day: date = TUESDAY, overrides: dict[str, tuple] | None = None, range_bar: tuple = RANGE,
              minutes: int = 1, drop: tuple[str, str] | None = None, quiet_bar: tuple = QUIET) -> pd.DataFrame:
    """Bars of `minutes` for all of `day`, New York wall clock: `range_bar` 09:30-09:45, `quiet_bar` elsewhere.

    `overrides` replaces bars by "HH:MM" ET; `drop` leaves out the bars in ["HH:MM", "HH:MM").
    """
    overrides = overrides or {}
    rows = []
    for stamp in pd.date_range(pd.Timestamp(day), periods=24 * 60 // minutes, freq=f"{minutes}min"):
        key = stamp.strftime("%H:%M")
        if drop is not None and drop[0] <= key < drop[1]:
            continue
        default = range_bar if "09:30" <= key < "09:45" else quiet_bar
        rows.append((stamp, *overrides.get(key, default)))
    return pd.DataFrame(rows, columns=["datetime", "open", "high", "low", "close"])


def range_at(hhmm: str, minutes: int = 15) -> dict[str, tuple]:
    """`day_frame` overrides putting the RANGE bars in the `minutes` from "HH:MM" ET (pass `range_bar=QUIET`)."""
    start = pd.Timestamp(f"2000-01-01 {hhmm}")
    return {(start + pd.Timedelta(minutes=m)).strftime("%H:%M"): RANGE for m in range(minutes)}


def data(*frames: pd.DataFrame, timezone=UTC, timeframe: str = "1m") -> HistoricalData:
    """`frames` (New York wall clock) relabelled to `timezone`, as one dataset."""
    frame = pd.concat(frames or [day_frame()], ignore_index=True)
    frame = shift_timezone(frame, timezone, from_tz=NEW_YORK)
    return HistoricalData(frame, SampleSize.Parse(timeframe), EURUSD, timezone=timezone)
