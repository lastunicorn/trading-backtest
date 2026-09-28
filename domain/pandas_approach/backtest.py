"""`Backtest`: run one strategy over one dataset under one set of simulation rules.

    from domain.pandas_approach.backtest import Backtest

    result = Backtest(strategy, data, cost=FixedCost(pips=1.7)).run()
    result.trades                                   # one row per trade, P&L and split included
    result.statistics.loc["all", "win_rate_pct"]    # rows: all, discovery, validation, test

`run()` goes strategy -> open positions -> `simulate_positions` -> costs ->
per-trade P&L -> discovery/validation/test split -> statistics, and returns
the numbers. It is a pure calculation: no files, no clock, no git. Recording
provenance and writing results is `application.run_backtest_use_case`'s job.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from domain.pandas_approach.cost_model import CostModel, FixedCost
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import positions_to_frame
from domain.pandas_approach.simulation import AmbiguityPolicy, ResolveFrom, simulate_positions
from domain.pandas_approach.splits import assign_splits, split_dates
from domain.pandas_approach.statistics import statistics_by_split
from domain.pandas_approach.trade_results import trade_results
from domain.pandas_approach.trading_strategy import TradingStrategy

__all__ = ["Backtest", "BacktestResult"]


@dataclass(frozen=True)
class BacktestResult:
    """What a run produced: the trades and their statistics."""

    # positions_to_frame + trade_results columns, plus "split" when splitting;
    # sorted by open_dt.
    trades: pd.DataFrame

    # statistics_by_split: rows "all" then one per split.
    statistics: pd.DataFrame


@dataclass
class Backtest:
    """One strategy, one dataset, one set of simulation rules."""

    strategy: TradingStrategy
    data: HistoricalData
    cost_model: CostModel = field(default_factory=FixedCost)
    ambiguity_policy: AmbiguityPolicy = AmbiguityPolicy.EXCLUDE
    resolve_from: ResolveFrom = ResolveFrom.NEXT_BAR
    # Report per discovery/validation/test split as well as overall.
    splits: bool = True

    def run(self) -> BacktestResult:
        positions = self.strategy.generate_positions(self.data)
        simulate_positions(self.data, positions, ambiguity=self.ambiguity_policy, resolve_from=self.resolve_from)

        trades = positions_to_frame(positions)
        trades = trade_results(trades, self.data.symbol, self.cost_model.cost_pips(trades, self.data))
        trades = trades.sort_values("open_dt", kind="stable").reset_index(drop=True)

        if self.splits:
            by_date = split_dates(self.strategy.split_days(self.data))
            trades["split"] = assign_splits(trades["open_dt"], by_date)

        return BacktestResult(trades=trades, statistics=statistics_by_split(trades))
