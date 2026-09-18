"""Relative Strength Index -- Wilder's smoothed RSI.

    from domain.rsi import rsi
    df["rsi"] = rsi(df["close"], length=14)

Matches Pine's `ta.rsi`: gains and losses smoothed with Wilder's RMA -- `na`
for the first `length` bars (not enough history to average yet), seeded at
bar `length` by the simple average of those `length` gains/losses, then
smoothed recursively (`avg[i] = (avg[i-1] * (length - 1) + x[i]) / length`)
from there on. A plain `ewm(adjust=False)` seeds from the first single
observation instead and never returns `na`, which looks fine but is wrong:
on real EURUSD M5 data it disagrees with the seeded version by up to ~30 RSI
points before converging around 6x `length` bars in -- exactly the "false
data at the start of the series" this function used to produce.
"""

from __future__ import annotations

import pandas as pd

__all__ = ["rsi"]


def _wilder_average(x: pd.Series, length: int) -> pd.Series:
    """Wilder's RMA: `na` for the first `length` values, SMA-seeded after."""
    result = pd.Series(float("nan"), index=x.index)
    if len(x) <= length:
        return result

    # `x[0]` is `close.diff()`'s leading NaN, so the first `length` usable
    # values -- the seed -- are positions 1..length.
    seed = x.iloc[1:length + 1].mean()
    result.iloc[length] = seed

    tail = x.iloc[length + 1:]
    if not tail.empty:
        # Prepending the seed lets one `ewm(adjust=False)` call carry out the
        # recursion from bar `length + 1` onward, vectorized rather than a
        # Python loop over the whole series.
        seeded = pd.concat([pd.Series([seed]), tail], ignore_index=True)
        result.iloc[length + 1:] = seeded.ewm(alpha=1 / length, adjust=False).mean().iloc[1:].to_numpy()

    return result


def rsi(close: pd.Series, length: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = _wilder_average(gain, length)
    avg_loss = _wilder_average(loss, length)

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))
