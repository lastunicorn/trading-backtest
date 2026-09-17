"""Relative Strength Index -- Wilder's smoothed RSI.

    from domain.rsi import rsi
    df["rsi"] = rsi(df["close"], length=14)

Matches Pine's `ta.rsi`: gains and losses smoothed with Wilder's RMA, the same
`ewm(alpha=1/length, adjust=False)` smoothing this repo already uses for ATR
(eurusd_narrow_asia_reversion_v26_1.py).
"""

from __future__ import annotations

import pandas as pd

__all__ = ["rsi"]


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False).mean()

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
