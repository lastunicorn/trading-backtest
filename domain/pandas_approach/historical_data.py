"""`HistoricalData`: a clean bar frame plus what it takes to interpret it.

    from domain.pandas_approach.historical_data import HistoricalData, SpreadUnit
    from domain.sample_size import SampleSize
    from domain.symbol import EurUsd

    data = HistoricalData.from_frame(frame, SampleSize.Parse("5m"), EurUsd(), spread_unit=SpreadUnit.POINTS)
    data.data            # the frame
    data.start_dt, data.end_dt, len(data)
    data.locate([t1, t2])  # row index of the bar each time falls in

The frame holds one bar per row, prices on the **bid** side:

    datetime      datetime64, naive, strictly increasing   required
    open/high/low/close   float64, no NaN                  required
    tick_volume, volume   Int64 (nullable)                  optional
    spread                float64, in pips                  optional

Extra columns pass through untouched. `datetime` is a naive wall-clock time
in `timezone` -- the broker's server time unless the frame was shifted (see
`domain.pandas_approach.shift_timezone`).

Two ways in. The constructor only *validates*: it never changes the frame, so
a wrong frame fails loudly instead of being quietly fixed. `from_frame`
*normalises* first -- float volumes to Int64, spread to pips, OHLC to
float64 -- then validates. It does not sort or dedupe: that is
`domain.pandas_approach.frames.clean_frame`'s job, and a frame that needs it
is rejected so the caller notices.

Spread is where the sources disagree: MT5 exports it in points (1 point =
the symbol's tick size, so 10 points = 1 pip on EURUSD), Dukascopy's reader
returns price units (ask - bid). `SpreadUnit` names which one a frame carries.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, tzinfo
from enum import Enum

import numpy as np
import pandas as pd

from domain.pandas_approach.shift_timezone import BROKER_SERVER_TZ
from domain.sample_size import SampleSize
from domain.symbol import Symbol

__all__ = ["HistoricalData", "SpreadUnit"]

_OHLC = ("open", "high", "low", "close")
_VOLUMES = ("tick_volume", "volume")


class SpreadUnit(Enum):
    """The unit a source frame's `spread` column is in."""

    PIPS = "pips"
    # Multiples of the symbol's tick size -- MT5's convention.
    POINTS = "points"
    # Raw price difference (ask - bid) -- Dukascopy's reader.
    PRICE = "price"


# eq=False: comparing two DataFrames with == is element-wise, not a bool, so
# the generated __eq__ would raise. Identity equality is the honest default.
@dataclass(frozen=True, eq=False)
class HistoricalData:
    """Bars for one symbol at one timeframe. Don't mutate `data` in place."""

    data: pd.DataFrame
    timeframe: SampleSize
    symbol: Symbol
    timezone: tzinfo = BROKER_SERVER_TZ

    def __post_init__(self) -> None:
        frame = self.data

        missing = [c for c in ("datetime", *_OHLC) if c not in frame.columns]
        if missing:
            raise ValueError(f"historical data is missing required column(s): {missing}")

        if frame.empty:
            raise ValueError("historical data has no bars")

        stamps = frame["datetime"]
        if not pd.api.types.is_datetime64_dtype(stamps):
            raise ValueError(
                f"'datetime' must be a naive datetime64 column, got {stamps.dtype} "
                "(timezone-aware stamps: drop the tz and set `timezone` instead)"
            )

        if not (stamps.is_monotonic_increasing and stamps.is_unique):
            raise ValueError(
                "'datetime' must be strictly increasing -- "
                "run domain.pandas_approach.frames.clean_frame first"
            )

        for column in _OHLC:
            if not pd.api.types.is_float_dtype(frame[column]):
                raise ValueError(f"'{column}' must be float, got {frame[column].dtype}")
            if frame[column].isna().any():
                raise ValueError(f"'{column}' has missing values")

        for column in _VOLUMES:
            if column in frame.columns and not pd.api.types.is_integer_dtype(frame[column]):
                raise ValueError(f"'{column}' must be an integer column, got {frame[column].dtype}")

        if "spread" in frame.columns and not pd.api.types.is_float_dtype(frame["spread"]):
            raise ValueError(f"'spread' must be float (pips), got {frame['spread'].dtype}")

    @classmethod
    def from_frame(
        cls,
        frame: pd.DataFrame,
        timeframe: SampleSize,
        symbol: Symbol,
        *,
        spread_unit: SpreadUnit = SpreadUnit.PIPS,
        timezone: tzinfo = BROKER_SERVER_TZ,
    ) -> HistoricalData:
        """Normalise a reader's frame into the documented layout, then validate.

        Works on a copy; `frame` itself is left alone. Volumes must hold whole
        numbers (the canonical M5 CSV stores `31.0`); a fractional volume
        raises rather than being rounded.
        """
        frame = frame.copy()

        for column in _OHLC:
            if column in frame.columns:
                frame[column] = frame[column].astype("float64")

        for column in _VOLUMES:
            if column in frame.columns:
                frame[column] = _to_nullable_int(frame[column], column)

        if "spread" in frame.columns:
            frame["spread"] = _spread_in_pips(frame["spread"].astype("float64"), spread_unit, symbol)

        return cls(frame, timeframe, symbol, timezone)

    @property
    def start_dt(self) -> datetime:
        """Timestamp of the first bar."""
        return self.data["datetime"].iat[0]

    @property
    def end_dt(self) -> datetime:
        """Timestamp of the last bar (its open time, not the end of its interval)."""
        return self.data["datetime"].iat[-1]

    def __len__(self) -> int:
        return len(self.data)

    def locate(self, stamps: Iterable[datetime]) -> np.ndarray:
        """Row index of the bar each stamp falls in: the last bar opening at or before it.

        A bar is taken to run until the next one opens, so a stamp inside a
        weekend gap lands on Friday's last bar. -1 marks a stamp with no bar:
        before the first one, or missing (`None`/`NaT`).
        """
        wanted = pd.to_datetime(pd.Series(list(stamps), dtype="object")).to_numpy()
        index = np.searchsorted(self.data["datetime"].to_numpy(), wanted, side="right") - 1
        index[pd.isna(wanted)] = -1
        return index


def _to_nullable_int(values: pd.Series, name: str) -> pd.Series:
    if pd.api.types.is_integer_dtype(values):
        return values.astype("Int64")

    present = values.dropna()
    if not (present % 1 == 0).all():
        raise ValueError(f"'{name}' has non-integral values; refusing to round them")

    return values.astype("Int64")


def _spread_in_pips(spread: pd.Series, unit: SpreadUnit, symbol: Symbol) -> pd.Series:
    if unit == SpreadUnit.PIPS:
        return spread
    if unit == SpreadUnit.POINTS:
        return symbol.to_pips(spread * symbol.tick_size)
    return symbol.to_pips(spread)
