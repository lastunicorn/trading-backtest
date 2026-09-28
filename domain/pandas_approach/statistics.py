"""Aggregate statistics over a set of trades.

    from domain.pandas_approach.statistics import compute_statistics, statistics_by_split

    stats = compute_statistics(trades)          # {"trades": 207, "win_rate_pct": 72.0, ...}
    table = statistics_by_split(trades)         # rows: all, discovery, validation, test

`trades` is a `trade_results` frame. Every P&L figure is **net of costs**, and
a trade is a win when `net_pips > 0`. That is not the same as hitting TP: a TP
closer than the cost is still a loss. Both views are reported, as the outcome
counts and the win/loss split.

Only *resolved* trades -- ones with a `net_pips` value -- enter the P&L
figures. AMBIGUOUS trades under the EXCLUDE policy are counted in
`trades`/`outcome_*` and reported as `excluded_ambiguous`, but carry no P&L.

The formulas follow v28's `summarize`, `max_drawdown` and
`max_consecutive_losses`, copied rather than imported (the vNN scripts are
immutable). Two deliberate differences: a loss is `net_pips <= 0` in the
streak count too (v28 used `< 0` there but `<= 0` for the loss count), and
profit factor is NaN rather than inf when there is no P&L at all.

Drawdown and streaks follow the trades in `open_dt` order.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

from domain.pandas_approach.position import PositionOutcome
from domain.pandas_approach.splits import Split

__all__ = ["compute_statistics", "max_consecutive_losses", "max_drawdown", "statistics_by_split"]


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


def statistics_by_split(trades: pd.DataFrame) -> pd.DataFrame:
    """One row of `compute_statistics` for all trades, then one per split.

    Every split gets a row even when it has no trades, so a missing split shows
    up as zeros rather than vanishing. Without a `split` column, only "all".
    """
    rows = {"all": compute_statistics(trades)}

    if "split" in trades.columns:
        for split in Split:
            rows[split.value] = compute_statistics(trades[trades["split"] == split.value])

    return pd.DataFrame.from_dict(rows, orient="index")


def _profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss > 0:
        return gross_profit / gross_loss
    return float("inf") if gross_profit > 0 else float("nan")
