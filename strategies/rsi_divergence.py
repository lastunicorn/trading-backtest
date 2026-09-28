"""RSI divergence reversal: `rsi_divergence_strategy.py`'s entries, plus exit levels.

    from strategies.rsi_divergence import RsiDivergence

    positions = RsiDivergence(risk_reward=2.0).generate_positions(data)   # built on M15 bars

Entries are exactly the scan script's (see `domain.pandas_approach.divergence`
and `divergence_positions.open_positions`):

  1. Wilder RSI(14); pivots 5 bars left / 5 right; two same-kind pivots 5-60
     bars apart where price and RSI disagree form a regular divergence.
  2. Only divergences whose older pivot's RSI is outside the 30/70 band and
     whose newer pivot's is inside it are kept. Below 30 -> long, above 70 ->
     short.
  3. Entry is the open of the first bar after the pivot is confirmed --
     `pivot_right + 1` bars after it. Entering on the pivot bar would be
     look-ahead.

Exits:

  - Stop: `stop_buffer_pips` beyond the price extreme of the newer pivot bar
    (its low for a long, its high for a short) -- the swing the divergence is
    drawn from.
  - Target: `risk_reward` x the entry-to-stop distance.

If price has already run past the pivot extreme by the entry bar's open, the
stop would sit on the wrong side of the entry; that signal is skipped.

Entries are at a bar's *open*, so the entry bar's range all happened after the
fill: run it with `"resolve_from": "entry-bar"`. The default next-bar rule would
ignore a stop or target hit on the entry bar itself.

    python3 backtest.py backtests/rsi_divergence     # timeframe 15m, resolve_from entry-bar

Timezone-agnostic: RSI and pivots depend on bar order, not the clock.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from domain.pandas_approach.divergence import filter_regular_by_band, find_divergences
from domain.pandas_approach.divergence_positions import open_positions
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.pandas_approach.rsi import rsi
from domain.pandas_approach.trading_strategy import TradingStrategy

__all__ = ["RsiDivergence"]


@dataclass(frozen=True)
class RsiDivergence(TradingStrategy):
    rsi_length: int = 14
    pivot_left: int = 5
    pivot_right: int = 5
    range_lower: int = 5
    range_upper: int = 60
    rsi_lower: float = 30
    rsi_upper: float = 70
    risk_reward: float = 2.0
    stop_buffer_pips: float = 1.0

    def __post_init__(self) -> None:
        if self.risk_reward <= 0:
            raise ValueError(f"risk_reward must be positive, got {self.risk_reward}")
        if self.stop_buffer_pips < 0:
            raise ValueError(f"stop_buffer_pips cannot be negative, got {self.stop_buffer_pips}")

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        frame = data.data

        # Find divergences
        divergences = find_divergences(
            frame,
            rsi(frame["close"], length=self.rsi_length),
            pivot_left=self.pivot_left,
            pivot_right=self.pivot_right,
            range_lower=self.range_lower,
            range_upper=self.range_upper,
            include_hidden=False,
        )

        # Keep regular divergences that fall within the specified RSI band
        divergences = filter_regular_by_band(divergences, self.rsi_lower, self.rsi_upper)
        signals = open_positions(
            frame, divergences, pivot_right=self.pivot_right, rsi_lower=self.rsi_lower, rsi_upper=self.rsi_upper,
        )

        pivot_rows = data.locate(signal.divergence.end_time for signal in signals)
        buffer = self.stop_buffer_pips * data.symbol.pip_size

        positions = []
        for signal, pivot_row in zip(signals, pivot_rows):
            entry_price = float(signal.open_price)

            if signal.side == Side.LONG:
                sl = float(frame["low"].iat[pivot_row]) - buffer
                if not sl < entry_price:
                    continue
                tp = entry_price + self.risk_reward * (entry_price - sl)
            else:
                sl = float(frame["high"].iat[pivot_row]) + buffer
                if not sl > entry_price:
                    continue
                tp = entry_price - self.risk_reward * (sl - entry_price)

            direction = "bullish" if signal.side == Side.LONG else "bearish"

            positions.append(Position(
                open_dt=pd.Timestamp(signal.open_time),
                open_price=entry_price,
                side=signal.side,
                sl=sl,
                tp=tp,
                tag=f"{direction} divergence, pivot {signal.divergence.end_time:%Y-%m-%d %H:%M}",
            ))

        return positions
