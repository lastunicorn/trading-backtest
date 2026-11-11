"""Aggregate statistics over a set of trades.

    from domain.backtesting.statistics import compute_statistics, statistics_by_split

    stats = compute_statistics(trades)          # {"trades": 207, "win_rate_pct": 72.0, ...}
    table = statistics_by_split(trades)         # rows: all, discovery, validation, test
    split_verdict(table).holds_in_every_split   # was every split net positive?

`trades` is a `trade_results` frame. Every P&L figure is **net of costs**, and
a trade is a win when `net_pips > 0`. That is not the same as hitting TP: a TP
closer than the cost is still a loss. Both views are reported, as the outcome
counts and the win/loss split.

Only *resolved* trades -- ones with a `net_pips` value -- enter the P&L
figures. AMBIGUOUS trades under the EXCLUDE policy are counted in
`trades`/`outcome_*` and reported as `excluded_ambiguous`, but carry no P&L.

A loss is `net_pips <= 0`, in the loss count and the losing-streak count
alike, and profit factor is NaN rather than inf when there is no P&L at all.

Drawdown and streaks follow the trades in `open_dt` order.

`split_verdict` is the methodology's test of a split result: a result only
counts when it holds in every split, so it says which splits ended net
positive (and which traded at all).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from domain.backtesting.position import PositionOutcome

__all__ = [
    "SplitVerdict", "compute_statistics", "max_consecutive_losses", "max_drawdown", "split_verdict",
    "statistics_by_split",
]


@dataclass(frozen=True)
class SplitVerdict:
    """Which splits of a `statistics_by_split` table traded, and which ended net positive.

    A split is net positive when its `total_net_pips > 0`; one without
    resolved trades (NaN) is not.
    """

    splits: tuple[str, ...]         # every split, in table order
    traded: tuple[str, ...]         # those with at least one trade
    net_positive: tuple[str, ...]   # those with total_net_pips > 0

    @property
    def holds_in_every_split(self) -> bool:
        """Every split is net positive, including those without trades (true when there are none)."""
        return len(self.net_positive) == len(self.splits)


def max_drawdown(net_pips: Sequence[float]) -> float:
    """Largest peak-to-trough drop of the cumulative P&L, starting from 0. NaN with no trades."""
    values = np.asarray(net_pips, dtype=float)
    if len(values) == 0:
        return float("nan")

    equity = np.concatenate([[0.0], np.cumsum(values)])
    peak = np.maximum.accumulate(equity)
    return float(np.max(peak - equity))


def max_consecutive_losses(net_pips: Sequence[float]) -> int:
    """Longest run of trades with `net_pips <= 0`."""
    longest = current = 0
    for value in net_pips:
        current = current + 1 if value <= 0 else 0
        longest = max(longest, current)
    return longest


def compute_statistics(trades: pd.DataFrame) -> dict[str, float]:
    """Every statistic for `trades`, in report order. An empty frame gives counts of 0 and NaN elsewhere."""
    ordered = trades.sort_values("open_dt", kind="stable")
    outcomes = ordered["outcome"].value_counts()

    stats: dict[str, float] = {"trades": len(ordered)}
    for outcome in PositionOutcome:
        stats[f"outcome_{outcome.value}"] = int(outcomes.get(outcome.value, 0))

    resolved = ordered[ordered["net_pips"].notna()]
    net = resolved["net_pips"]
    wins = net[net > 0]
    losses = net[net <= 0]

    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())

    stats.update({
        "excluded_ambiguous": stats[f"outcome_{PositionOutcome.AMBIGUOUS.value}"],
        "resolved": len(resolved),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": 100 * len(wins) / len(resolved) if len(resolved) else float("nan"),
        "total_gross_pips": float(resolved["gross_pips"].sum()) if len(resolved) else float("nan"),
        "total_cost_pips": float(resolved["cost_pips"].sum()) if len(resolved) else float("nan"),
        "total_net_pips": float(net.sum()) if len(resolved) else float("nan"),
        "total_net_r": float(resolved["net_r"].sum()) if len(resolved) else float("nan"),
        "avg_net_pips": float(net.mean()),
        "median_net_pips": float(net.median()),
        "avg_win_pips": float(wins.mean()),
        "avg_loss_pips": float(losses.mean()),
        "profit_factor": _profit_factor(gross_profit, gross_loss),
        "expectancy_r": float(resolved["net_r"].mean()),
        "max_drawdown_pips": max_drawdown(net),
        "max_consecutive_losses": max_consecutive_losses(net),
        "avg_duration_min": float(resolved["duration_min"].mean()),
    })
    return stats


def statistics_by_split(trades: pd.DataFrame, splits: Sequence[str] = ()) -> pd.DataFrame:
    """One row of `compute_statistics` for all trades, then one per name in `splits`, in order.

    Every split named gets a row even when it has no trades, so a missing split
    shows up as zeros rather than vanishing. With no `splits`, only "all".
    """
    rows = {"all": compute_statistics(trades)}

    for split in splits:
        rows[split] = compute_statistics(trades[trades["split"] == split])

    return pd.DataFrame.from_dict(rows, orient="index")


def split_verdict(table: pd.DataFrame) -> SplitVerdict:
    """The verdict on the splits of a `statistics_by_split` table: every row after "all"."""
    splits = table.drop(index="all")
    return SplitVerdict(
        splits=tuple(splits.index),
        traded=tuple(splits.index[splits["trades"] > 0]),
        net_positive=tuple(splits.index[splits["total_net_pips"] > 0]),
    )


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss > 0:
        return gross_profit / gross_loss
    return float("inf") if gross_profit > 0 else float("nan")
