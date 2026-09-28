"""Simulated positions opened off confirmed regular RSI divergences.

    from domain.pandas_approach.divergence_positions import open_positions
    positions = open_positions(df, divergences, pivot_right=5, rsi_lower=30, rsi_upper=70)
    for p in positions:
        print(p.side.value, p.open_time, p.open_price)

A divergence's `end_time` is the pivot bar itself, but `find_divergences`
only recognises that bar as a pivot once `pivot_right` bars after it exist
(`ta.pivotlow`/`ta.pivothigh`'s confirmation delay -- see
`domain.pandas_approach.divergence`). A position entered right on `end_time`
would be look-ahead: nobody watching the oscillator live could have known
about the divergence yet. The earliest honest entry is the open of the bar
right after confirmation, i.e. `pivot_right + 1` bars after `end_time`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from domain.pandas_approach.divergence import Category, Divergence
from domain.pandas_approach.side import Side

__all__ = ["DivergencePosition", "open_positions"]


@dataclass(frozen=True, slots=True)
class DivergencePosition:
    """An entry signal tied to the divergence that produced it.

    Predates the backtest framework's `domain.pandas_approach.position.Position`
    and carries no SL/TP; it goes away once the RSI divergence strategy is
    ported onto `TradingStrategy`."""

    divergence: Divergence
    side: Side
    open_time: datetime
    open_price: float


def open_positions(
    df: pd.DataFrame,
    divergences: list[Divergence],
    *,
    pivot_right: int,
    rsi_lower: float,
    rsi_upper: float,
) -> list[DivergencePosition]:
    """One position per regular divergence starting outside the 30/70 band.

    `df` needs `datetime` and `open` columns aligned with the frame
    `divergences` was computed from. Hidden divergences carry no 30/70
    signal and are skipped. A divergence too close to the end of `df` to
    have a confirmed entry bar yet is skipped too.
    """
    entry_idx_by_time = pd.Series(range(len(df)), index=df["datetime"].to_numpy())

    positions = []
    for divergence in divergences:
        if divergence.category != Category.REGULAR:
            continue

        if divergence.start_value < rsi_lower:
            side = Side.LONG
        elif divergence.start_value > rsi_upper:
            side = Side.SHORT
        else:
            continue

        pivot_idx = entry_idx_by_time.at[pd.Timestamp(divergence.end_time)]
        entry_idx = pivot_idx + pivot_right + 1
        if entry_idx >= len(df):
            continue

        positions.append(DivergencePosition(
            divergence=divergence,
            side=side,
            open_time=df["datetime"].iat[entry_idx],
            open_price=df["open"].iat[entry_idx],
        ))

    return positions
