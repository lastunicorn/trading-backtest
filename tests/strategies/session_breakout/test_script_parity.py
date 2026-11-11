"""Acceptance test: the port reproduces `session_breakout_strategy.py` trade for trade.

The script is deleted; `_script_trades.SCRIPT_TRADES` holds what it produced
on this synthetic M1 random walk -- six broker-clock weeks spanning the March
2026 US daylight-saving switch. The port gets the broker-clock frame and is
backtested with the parity settings (entry-bar, exclude, no costs).

The script left force-closed positions without a price, so those are
compared on outcome and time only. A failure here is a port bug.
"""

from datetime import UTC

import numpy as np
import pandas as pd

from domain.backtesting.backtest import AmbiguityPolicy, Backtest
from domain.backtesting.cost_model import FixedCost
from domain.market_data.historical_data import HistoricalData
from domain.backtesting.position import PositionOutcome
from domain.market_data.shift_timezone import shift_timezone
from domain.market_data.sample_size import SampleSize
from domain.market_data.symbol import EURUSD
from strategies.session_breakout import SessionBreakout
from ._script_trades import SCRIPT_TRADES

_PIP = 0.0001


def _random_walk() -> pd.DataFrame:
    """M1 bars, broker clock, Monday 00:00 to Friday 23:59 each week."""
    stamps = pd.date_range("2026-02-16", "2026-03-27 23:59", freq="1min")
    stamps = stamps[stamps.dayofweek < 5]

    rng = np.random.default_rng(20260929)
    close = np.round(1.1 + np.cumsum(rng.normal(0, 0.4 * _PIP, len(stamps))), 5)
    open_ = np.concatenate([[1.1], close[:-1]])
    high = np.round(np.maximum(open_, close) + np.abs(rng.normal(0, 0.3 * _PIP, len(stamps))), 5)
    low = np.round(np.minimum(open_, close) - np.abs(rng.normal(0, 0.3 * _PIP, len(stamps))), 5)
    return pd.DataFrame({"datetime": stamps, "open": open_, "high": high, "low": low, "close": close})


def _port_trades(frame: pd.DataFrame, max_range_pips: float, risk_reward: float) -> list[tuple]:
    data = HistoricalData(frame, SampleSize.Parse("1m"), EURUSD)
    backtest = Backtest(
        SessionBreakout(max_range_pips=max_range_pips, risk_reward=risk_reward, check_trigger_bar=True),
        data,
        cost_model=FixedCost(pips=0.0),
        ambiguity_policy=AmbiguityPolicy.EXCLUDE,
    )
    trades = backtest.run().trades.copy()

    # The script force-closes at the time stop even when the data ran out first.
    ran_out = trades["outcome"] == PositionOutcome.END_OF_DATA.value
    trades.loc[ran_out, "outcome"] = PositionOutcome.MANUAL_CLOSE.value
    trades.loc[ran_out, "close_dt"] = trades.loc[ran_out, "exit_dt"]

    def to_utc(column: str) -> pd.Series:
        return shift_timezone(trades[[column]].rename(columns={column: "datetime"}), UTC)["datetime"]

    priced = (PositionOutcome.TAKE_PROFIT_HIT.value, PositionOutcome.STOP_LOSS_HIT.value)
    return sorted(
        (
            f"{open_dt:%Y-%m-%d %H:%M}", row.side, row.open_price, row.sl, row.tp, row.outcome,
            f"{close_dt:%Y-%m-%d %H:%M}", row.close_price if row.outcome in priced else None,
        )
        for row, open_dt, close_dt in zip(trades.itertuples(index=False), to_utc("open_dt"), to_utc("close_dt"))
    )


def test_reproduces_the_script_trade_for_trade() -> None:
    frame = _random_walk()

    for (max_range_pips, risk_reward), script in SCRIPT_TRADES.items():
        port = _port_trades(frame, max_range_pips, risk_reward)

        assert len(script) > 20                                   # the walk actually trades
        assert {t[5] for t in script} >= {"take-profit-hit", "stop-loss-hit", "manual-close"}
        assert port == script
