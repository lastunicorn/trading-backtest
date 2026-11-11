"""`Backtest`: run one strategy over one dataset under one set of simulation rules.

    from domain.backtesting.backtest import AmbiguityPolicy, Backtest
    from domain.backtesting.splits import SplitMode

    result = Backtest(strategy, data, cost_model=FixedCost(pips=1.7), splits=SplitMode.DVT).run()
    result.trades                                   # one row per trade, P&L and split included
    result.statistics.loc["all", "win_rate_pct"]    # rows: all, discovery, validation, test
    result.verdict.holds_in_every_split             # net positive in discovery, validation and test?
    result.strategy, result.data.first_bar          # what ran, on what, under which rules

`run()` goes strategy -> open positions -> exits (`_simulate`) -> costs ->
per-trade P&L -> split (`SplitMode`, none by default) -> statistics, and returns
the numbers together with what describes the run, so a `BacktestResult` can be
reported on its own. It is a pure calculation: no files, no clock, no git.
Recording provenance and writing results is the `backtest.py` CLI's job.

`_simulate` is the one place exit logic lives, so strategies only decide
entries. Each position is walked independently from its entry bar to its time
stop (or the end of the data); there is no portfolio, no position sizing, and
positions don't know about each other.

The exit rules, all on bid OHLC (see `HistoricalData`):

- **Hits.** A long hits TP when a bar's high reaches it and SL when its low
  does; a short mirrors that. The fill is the level itself. That includes a bar
  that *gaps* through the level, so SL fills are optimistic after gaps.
- **Where checking starts** is each position's `entry_fill`. AT_LEVEL (the
  default) skips the entry bar, because an entry at a level *inside* the bar
  can't tell whether the bar's extremes came before or after the fill. AT_OPEN
  checks the entry bar too: the whole bar comes after a fill at its open.
- **One bar touching both levels** is ambiguous: OHLC can't say which came
  first. `AmbiguityPolicy` decides. EXCLUDE (the repo's research convention)
  closes it as AMBIGUOUS with no price, so it drops out of P&L. ASSUME_SL
  and ASSUME_TP settle it as that level.
- **Time stop.** With `exit_dt` set, only bars opening before `exit_dt` are
  traded. If none of them hits, the position closes MANUAL_CLOSE at the close
  of the last of them (the price at `exit_dt`), with `close_dt = exit_dt`.
- **End of data.** When the bars run out first -- no `exit_dt`, or no bar at or
  after it -- the position closes END_OF_DATA at the last bar's close.

`close_dt` of a hit is the hitting bar's timestamp (its open time), because
OHLC doesn't say when inside the bar it happened.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np
import pandas as pd

from domain.backtesting.cost_model import CostModel, FixedCost
from domain.pandas_approach.historical_data import DataSummary, HistoricalData
from domain.backtesting.position import EntryFill, Position, PositionOutcome, Side, positions_to_frame
from domain.backtesting.splits import SplitMode, assign_splits, split_labels
from domain.backtesting.statistics import SplitVerdict, split_verdict, statistics_by_split
from domain.backtesting.trade_results import trade_results
from domain.backtesting.trading_strategy import TradingStrategy

__all__ = ["AmbiguityPolicy", "Backtest", "BacktestResult"]


class AmbiguityPolicy(Enum):
    """What to do when one bar touches both SL and TP."""

    EXCLUDE = "exclude"
    ASSUME_SL = "assume-sl"
    ASSUME_TP = "assume-tp"


@dataclass(frozen=True)
class BacktestResult:
    """A finished run: what ran, on what, under which rules, and what it produced.

    The first five fields are the `Backtest`'s settings, the data as a summary.
    """

    strategy: TradingStrategy
    data: DataSummary
    cost_model: CostModel
    ambiguity_policy: AmbiguityPolicy
    splits: SplitMode

    # positions_to_frame + trade_results columns, plus "split" when splitting;
    # sorted by open_dt.
    trades: pd.DataFrame

    # statistics_by_split: rows "all" then one per split.
    statistics: pd.DataFrame

    # split_verdict of `statistics`; None without splits (SplitMode.NONE).
    verdict: SplitVerdict | None

    # Caveats about how the numbers were produced (e.g. the cost model's), for the report.
    notes: tuple[str, ...] = ()


@dataclass
class Backtest:
    """One strategy, one dataset, one set of simulation rules."""

    strategy: TradingStrategy
    data: HistoricalData
    cost_model: CostModel = field(default_factory=FixedCost)
    ambiguity_policy: AmbiguityPolicy = AmbiguityPolicy.EXCLUDE
    # Report per split as well as overall: discovery/validation/test, month or year.
    splits: SplitMode = SplitMode.NONE

    def run(self) -> BacktestResult:
        positions = self.strategy.generate_positions(self.data)
        self._close_positions(positions)

        trades = positions_to_frame(positions)
        notes = tuple(self.cost_model.notes(trades, self.data))
        trades = trade_results(trades, self.data.symbol, self.cost_model.cost_pips(trades, self.data))
        trades = trades.sort_values("open_dt", kind="stable").reset_index(drop=True)

        names: list[str] = []
        if self.splits is not SplitMode.NONE:
            by_date = split_labels(self.strategy.split_days(self.data), self.splits)
            trades["split"] = assign_splits(trades["open_dt"], by_date)
            names = list(dict.fromkeys(by_date.values()))

        statistics = statistics_by_split(trades, names)
        return BacktestResult(
            strategy=self.strategy,
            data=self.data.summary(),
            cost_model=self.cost_model,
            ambiguity_policy=self.ambiguity_policy,
            splits=self.splits,
            trades=trades,
            statistics=statistics,
            verdict=split_verdict(statistics) if self.splits is not SplitMode.NONE else None,
            notes=notes,
        )

    def _close_positions(self, positions: list[Position]) -> None:
        """Close every position in place, under the exit rules in the module docstring.

        Positions must be open and must not open before the first bar; either
        mistake raises instead of being skipped, since a silently dropped trade
        changes every statistic.
        """
        for position in positions:
            if position.is_closed:
                raise ValueError(f"position opened at {position.open_dt} is already closed")

        frame = self.data.data
        times = frame["datetime"].to_numpy()
        high = frame["high"].to_numpy()
        low = frame["low"].to_numpy()
        close = frame["close"].to_numpy()

        entry_bars = self.data.locate(p.open_dt for p in positions)

        for position, entry_bar in zip(positions, entry_bars):
            if entry_bar < 0:
                raise ValueError(f"position opens at {position.open_dt}, before the first bar {self.data.start_dt}")

            first = entry_bar if position.entry_fill == EntryFill.AT_OPEN else entry_bar + 1

            # One past the last bar the position may trade on.
            if position.exit_dt is None:
                stop = len(times)
            else:
                # At the column's own unit: a mismatched one makes numpy convert all of `times` per position.
                stop = int(np.searchsorted(times, np.datetime64(position.exit_dt).astype(times.dtype), side="left"))
            # No bar at or after exit_dt means the data ran out before the time stop.
            ran_out = stop == len(times)

            if first < stop:
                self._resolve_hits(position, times, high, low, first, stop)

            if position.is_closed:
                continue

            last = stop - 1
            if ran_out:
                position.close(pd.Timestamp(times[last]), float(close[last]), PositionOutcome.END_OF_DATA)
            else:
                position.close(position.exit_dt, float(close[last]), PositionOutcome.MANUAL_CLOSE)

    def _resolve_hits(
        self,
        position: Position,
        times: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
        first: int,
        stop: int,
    ) -> None:
        """Close `position` on the first bar in [first, stop) touching SL or TP, if any."""
        highs = high[first:stop]
        lows = low[first:stop]

        if position.side == Side.LONG:
            hit_tp = highs >= position.tp
            hit_sl = lows <= position.sl
        else:
            hit_tp = lows <= position.tp
            hit_sl = highs >= position.sl

        hit_any = hit_tp | hit_sl
        if not hit_any.any():
            return

        offset = int(np.argmax(hit_any))
        at = pd.Timestamp(times[first + offset])

        if hit_tp[offset] and hit_sl[offset]:
            if self.ambiguity_policy == AmbiguityPolicy.EXCLUDE:
                position.close(at, None, PositionOutcome.AMBIGUOUS)
            elif self.ambiguity_policy == AmbiguityPolicy.ASSUME_SL:
                position.close(at, position.sl, PositionOutcome.STOP_LOSS_HIT)
            else:
                position.close(at, position.tp, PositionOutcome.TAKE_PROFIT_HIT)
        elif hit_tp[offset]:
            position.close(at, position.tp, PositionOutcome.TAKE_PROFIT_HIT)
        else:
            position.close(at, position.sl, PositionOutcome.STOP_LOSS_HIT)
