"""Shared builders for the `domain.pandas_approach.statistics` tests."""

import pandas as pd

T0 = pd.Timestamp("2026-01-05 10:00")


def trades(net_pips: list[float | None], *, outcomes: list[str] | None = None,
           splits: list[str] | None = None, cost: float = 1.0) -> pd.DataFrame:
    """A minimal trade_results frame: one trade per `net_pips` value, a day apart.

    None marks an ambiguous trade (no P&L). risk_pips is 10 and duration 60
    minutes for every trade.
    """
    n = len(net_pips)
    net = pd.Series(net_pips, dtype="float64")
    frame = pd.DataFrame({
        "open_dt": pd.date_range(T0, periods=n, freq="1D"),
        "outcome": outcomes or [
            "ambiguous" if v is None else "take-profit-hit" if v > 0 else "stop-loss-hit"
            for v in net_pips
        ],
        "gross_pips": net + cost,
        "cost_pips": [cost] * n,
        "net_pips": net,
        "risk_pips": [10.0] * n,
        "net_r": net / 10,
        "duration_min": [60.0] * n,
    })
    if splits is not None:
        frame["split"] = splits
    return frame
