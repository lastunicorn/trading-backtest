"""RSI divergence detection, translated from
`temp/RSI Divergence Indicator.pine` (the LuxAlgo-style regular/hidden
divergence indicator).

    from domain.divergence import find_divergences
    divergences = find_divergences(df, rsi_series)
    for d in divergences:
        print(d.category.value, d.direction.value, d.start_time, "->", d.end_time)

A pivot low (high) in the oscillator is a bar strictly lower (higher) than the
`pivot_left` bars before it and the `pivot_right` bars after it -- exactly
`ta.pivotlow`/`ta.pivothigh` in the Pine source. Each pivot is then compared
against the previous pivot of the same kind (Pine's `ta.valuewhen(..., 1)`):
if the gap between them falls inside `[range_lower, range_upper]` bars and
price and oscillator disagree on direction, that pair is a divergence.

    Regular Bullish -- price Lower Low,   RSI Higher Low
    Hidden Bullish  -- price Higher Low,  RSI Lower Low   (only with include_hidden)
    Regular Bearish -- price Higher High, RSI Lower High
    Hidden Bearish  -- price Lower High,  RSI Higher High (only with include_hidden)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd

__all__ = ["Category", "Direction", "Divergence", "filter_regular_by_band", "find_divergences"]


class Category(Enum):
    REGULAR = "Regular"
    HIDDEN = "Hidden"


class Direction(Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"


@dataclass(frozen=True, slots=True)
class Divergence:
    category: Category
    direction: Direction
    start_time: datetime
    end_time: datetime
    start_value: float
    end_value: float


def _pivots(values: np.ndarray, left: int, right: int, *, high: bool) -> np.ndarray:
    """Indices strictly more extreme than their `left`/`right` neighbours."""
    n = len(values)
    found = []

    for p in range(left, n - right):
        pivot = values[p]
        window_left = values[p - left:p]
        window_right = values[p + 1:p + right + 1]

        if high:
            is_pivot = (window_left < pivot).all() and (window_right <= pivot).all()
        else:
            is_pivot = (window_left > pivot).all() and (window_right >= pivot).all()

        if is_pivot:
            found.append(p)

    return np.array(found, dtype=np.int64)


def _bullish_divergences(
    pivot_idx: np.ndarray,
    osc: np.ndarray,
    low: np.ndarray,
    times: pd.Series,
    range_lower: int,
    range_upper: int,
    include_hidden: bool,
) -> list[Divergence]:
    out = []

    for prev_p, curr_p in zip(pivot_idx, pivot_idx[1:]):
        if not (range_lower <= curr_p - prev_p <= range_upper):
            continue

        price_ll = low[curr_p] < low[prev_p]
        price_hl = low[curr_p] > low[prev_p]
        osc_hl = osc[curr_p] > osc[prev_p]
        osc_ll = osc[curr_p] < osc[prev_p]

        if price_ll and osc_hl:
            out.append(Divergence(Category.REGULAR, Direction.BULLISH, times.iat[prev_p],
                                   times.iat[curr_p], osc[prev_p], osc[curr_p]))
        elif include_hidden and price_hl and osc_ll:
            out.append(Divergence(Category.HIDDEN, Direction.BULLISH, times.iat[prev_p],
                                   times.iat[curr_p], osc[prev_p], osc[curr_p]))

    return out


def _bearish_divergences(
    pivot_idx: np.ndarray,
    osc: np.ndarray,
    high: np.ndarray,
    times: pd.Series,
    range_lower: int,
    range_upper: int,
    include_hidden: bool,
) -> list[Divergence]:
    out = []

    for prev_p, curr_p in zip(pivot_idx, pivot_idx[1:]):
        if not (range_lower <= curr_p - prev_p <= range_upper):
            continue

        price_hh = high[curr_p] > high[prev_p]
        price_lh = high[curr_p] < high[prev_p]
        osc_lh = osc[curr_p] < osc[prev_p]
        osc_hh = osc[curr_p] > osc[prev_p]

        if price_hh and osc_lh:
            out.append(Divergence(Category.REGULAR, Direction.BEARISH, times.iat[prev_p],
                                   times.iat[curr_p], osc[prev_p], osc[curr_p]))
        elif include_hidden and price_lh and osc_hh:
            out.append(Divergence(Category.HIDDEN, Direction.BEARISH, times.iat[prev_p],
                                   times.iat[curr_p], osc[prev_p], osc[curr_p]))

    return out


def find_divergences(
    df: pd.DataFrame,
    oscillator: pd.Series,
    *,
    pivot_left: int = 5,
    pivot_right: int = 5,
    range_lower: int = 5,
    range_upper: int = 60,
    include_hidden: bool = False,
) -> list[Divergence]:
    """Every divergence between `oscillator` and `df`'s high/low, oldest first.

    `df` needs `datetime`, `high` and `low` columns aligned with `oscillator`
    (same index order, e.g. the M5 frame `build_clean_dataset` returns).
    """
    osc = oscillator.to_numpy()
    low = df["low"].to_numpy()
    high = df["high"].to_numpy()
    times = df["datetime"]

    pivot_lows = _pivots(osc, pivot_left, pivot_right, high=False)
    pivot_highs = _pivots(osc, pivot_left, pivot_right, high=True)

    divergences = _bullish_divergences(
        pivot_lows, osc, low, times, range_lower, range_upper, include_hidden
    ) + _bearish_divergences(
        pivot_highs, osc, high, times, range_lower, range_upper, include_hidden
    )

    divergences.sort(key=lambda d: d.end_time)
    return divergences


def filter_regular_by_band(divergences: list[Divergence], lower: float, upper: float) -> list[Divergence]:
    """Keep regular divergences that start outside [lower, upper] and end inside it.

    Those mark the oscillator actually leaving overbought/oversold territory
    (the 30/70 band by default in the callers). Hidden divergences pass
    through untouched: they occur mid-trend, not at the extremes the band is
    meant to isolate.
    """
    return [
        d for d in divergences
        if d.category != Category.REGULAR
        or (not (lower <= d.start_value <= upper) and lower <= d.end_value <= upper)
    ]
