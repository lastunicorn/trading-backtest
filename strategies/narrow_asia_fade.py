"""Candle DNA -- Narrow Asia London Fade: v28's frozen rule set as a `TradingStrategy`.

    from strategies.narrow_asia_fade import NarrowAsiaFade

    positions = NarrowAsiaFade().generate_positions(data)   # M5 bars, broker-server clock

For each weekday, in broker-server time:

  1. Asia (02:00-10:00) sets H and L. The day needs nearly all of Asia's bars
     (at most 3 missing) and an Asia range of at most 21.72 pips -- the
     discovery-Q1 threshold v28 froze.
  2. From London open (10:00) to study end (14:00, that bar included) the first
     bar to reach H or L is the break. A bar reaching both is ambiguous and the
     day is skipped. The break bar's relative volume (tick volume over its
     20-bar SMA) must be at least 1.6.
  3. From the bar after the break, the first bar trading back through the
     broken level is the entry: a short at H after an upside break, a long at L
     after a downside one.
  4. Target: the Asia midpoint. Stop: 1.00 x the Asia range beyond the entry.
     Still open after the 14:00 bar, it is closed at that bar's close.

Step 4's exits are the simulator's job. This class only emits the entries,
with `exit_dt` set to the end of the 14:00 bar. v28 resolved exits from the bar
after entry and settled a bar touching both SL and TP as a stop, so the parity
run is `AmbiguityPolicy.ASSUME_SL` with `PositionResolveDelay.NEXT_BAR`:

    python3 backtest.py --strategy narrow_asia_fade --ambiguity assume-sl --resolve-from next-bar \\
        --source output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv --out output/backtest_narrow_asia_fade

It reproduces v28's RANGE_MULT 1.00 line: 207 trades, 72.0% WR, PF 1.37,
+257.5 pips.

The windows are broker-server wall-clock times, so the data must be on that
clock (`BROKER_SERVER_TZ`); anything else raises rather than trading the
wrong hours. The two live ports -- `Candle_DNA_Narrow_Asia_London_Fade_v1.mq5`
and `pine version 6.txt` -- must stay in sync with these defaults.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time

import numpy as np
import pandas as pd

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.pandas_approach.trading_strategy import TradingStrategy
from domain.sample_size import SampleUnit

__all__ = ["NarrowAsiaFade"]


@dataclass(frozen=True)
class _AsiaDay:
    """One weekday with a usable Asia session: its bars' row range and the Asia levels."""

    day: date
    start: int    # first row of the day in the weekday frame
    stop: int     # one past its last row
    high: float
    low: float


@dataclass(frozen=True)
class NarrowAsiaFade(TradingStrategy):
    asia_start: time = time(2, 0)
    asia_end: time = time(10, 0)             # exclusive
    london_open: time = time(10, 0)
    study_end: time = time(14, 0)            # open time of the last bar traded
    narrow_threshold_pips: float = 21.72     # frozen: discovery Q1 of the Asia range
    rel_vol_min: float = 1.6
    rel_vol_length: int = 20
    stop_range_multiple: float = 1.0
    max_missing_asia_bars: int = 3

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        frame = self._weekdays(data)
        times = frame["datetime"].to_numpy()
        high = frame["high"].to_numpy()
        low = frame["low"].to_numpy()
        minute = _minute_of_day(frame)
        rel_vol = self._relative_volume(frame)
        pip = data.symbol.pip_size
        bar = self._bar_length(data)

        london_open = _minutes(self.london_open)
        study_end = _minutes(self.study_end)

        positions = []
        for asia in self._asia_days(data, frame):
            range_pips = data.symbol.to_pips(asia.high - asia.low)
            if range_pips > self.narrow_threshold_pips:
                continue

            rows = np.arange(asia.start, asia.stop)
            window = rows[(minute[rows] >= london_open) & (minute[rows] <= study_end)]

            up = high[window] >= asia.high
            down = low[window] <= asia.low
            broke = up | down
            if not broke.any():
                continue

            first = int(np.argmax(broke))
            if up[first] and down[first]:
                continue    # ambiguous break bar: which side came first is unknowable

            break_row = window[first]
            if not rel_vol[break_row] >= self.rel_vol_min:    # also rejects NaN
                continue

            after = window[first + 1:]
            broke_up = bool(up[first])
            back_inside = low[after] <= asia.high if broke_up else high[after] >= asia.low
            if not back_inside.any():
                continue

            entry_row = after[int(np.argmax(back_inside))]
            stop_distance = range_pips * self.stop_range_multiple * pip

            if broke_up:
                side, entry, sl, tag = Side.SHORT, asia.high, asia.high + stop_distance, "fade-high"
            else:
                side, entry, sl, tag = Side.LONG, asia.low, asia.low - stop_distance, "fade-low"

            positions.append(Position(
                open_dt=pd.Timestamp(times[entry_row]),
                open_price=entry,
                side=side,
                sl=sl,
                tp=(asia.high + asia.low) / 2,
                exit_dt=pd.Timestamp(datetime.combine(asia.day, self.study_end)) + bar,
                tag=tag,
            ))

        return positions

    def split_days(self, data: HistoricalData) -> list[date]:
        """Weekdays with a usable Asia session -- the days v28 cut its 60/20/20 split over."""
        return [asia.day for asia in self._asia_days(data, self._weekdays(data))]

    def _asia_days(self, data: HistoricalData, frame: pd.DataFrame) -> Iterator[_AsiaDay]:
        """Each weekday with nearly all of its Asia bars and a positive Asia range."""
        high = frame["high"].to_numpy()
        low = frame["low"].to_numpy()
        minute = _minute_of_day(frame)

        asia_start = _minutes(self.asia_start)
        asia_end = _minutes(self.asia_end)
        bar_minutes = self._bar_length(data) // pd.Timedelta(minutes=1)
        expected = max((asia_end - asia_start) // bar_minutes, 1)

        days = frame["datetime"].dt.date.to_numpy()
        # The frame is sorted, so each day is one contiguous run of rows.
        boundaries = np.flatnonzero(days[1:] != days[:-1]) + 1
        starts = np.concatenate([[0], boundaries])
        stops = np.concatenate([boundaries, [len(frame)]])

        for start, stop in zip(starts, stops):
            in_asia = (minute[start:stop] >= asia_start) & (minute[start:stop] < asia_end)
            if in_asia.sum() < expected - self.max_missing_asia_bars:
                continue

            asia_high = float(high[start:stop][in_asia].max())
            asia_low = float(low[start:stop][in_asia].min())
            if not asia_high > asia_low:
                continue

            yield _AsiaDay(days[start], int(start), int(stop), asia_high, asia_low)

    def _weekdays(self, data: HistoricalData) -> pd.DataFrame:
        """The bars v28 studied: Monday-Friday only, on the broker-server clock."""
        if data.timezone != BROKER_SERVER_TZ:
            raise ValueError(
                f"NarrowAsiaFade's windows are broker-server times; the data is on {data.timezone}"
            )
        frame = data.data
        return frame[frame["datetime"].dt.dayofweek < 5].reset_index(drop=True)

    def _relative_volume(self, frame: pd.DataFrame) -> np.ndarray:
        """Volume over its trailing SMA, bar by bar; NaN where there is no volume or no average yet."""
        column = "tick_volume" if "tick_volume" in frame.columns else "volume"
        if column not in frame.columns:
            return np.full(len(frame), np.nan)

        volume = pd.Series(frame[column].to_numpy(dtype="float64", na_value=np.nan))
        average = volume.rolling(self.rel_vol_length).mean()
        return np.where(average > 0, volume / average, np.nan)

    @staticmethod
    def _bar_length(data: HistoricalData) -> pd.Timedelta:
        if data.timeframe.unit != SampleUnit.Minute:
            raise ValueError(f"NarrowAsiaFade needs intraday minute bars, got {data.timeframe}")
        return pd.Timedelta(minutes=data.timeframe.amount)


def _minutes(at: time) -> int:
    return at.hour * 60 + at.minute


def _minute_of_day(frame: pd.DataFrame) -> np.ndarray:
    stamps = frame["datetime"]
    return (stamps.dt.hour * 60 + stamps.dt.minute).to_numpy()
