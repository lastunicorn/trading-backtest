"""Acceptance test: the port reproduces `session_breakout_strategy.py` trade for trade.

Both run on the same synthetic M1 random walk -- six broker-clock weeks
spanning the March 2026 US daylight-saving switch. The script gets the bars
shifted to UTC, as its own loader does; the port gets the broker-clock frame
and is backtested with the parity settings (entry-bar, exclude, no costs).

The script leaves force-closed positions without a price, so those are
compared on outcome and time only. A failure here is a port bug.
"""

from datetime import UTC

import numpy as np
import pandas as pd

from domain.bar_approach.bar import Bar
from domain.bar_approach.position import Outcome
from domain.bar_approach.shift_bars import shift_bars
from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, PositionCloseDelay
from domain.pandas_approach.cost_model import FixedCost
from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import PositionOutcome
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from session_breakout_strategy import SessionBreakoutStrategy
from strategies.session_breakout import SessionBreakout

_PIP = 0.0001

_OUTCOMES = {
    Outcome.TP_HIT: PositionOutcome.TAKE_PROFIT_HIT.value,
    Outcome.SL_HIT: PositionOutcome.STOP_LOSS_HIT.value,
    Outcome.AMBIGUOUS: PositionOutcome.AMBIGUOUS.value,
    Outcome.FORCE_CLOSED: PositionOutcome.MANUAL_CLOSE.value,
}


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


def _script_trades(frame: pd.DataFrame, max_range_pips: float, risk_reward: float) -> list[tuple]:
    sessions = []
    strategy = SessionBreakoutStrategy(
        max_range_pips=max_range_pips, risk_reward_ratio=risk_reward, on_session_closed=sessions.append,
    )
    bars = (Bar(row.datetime.to_pydatetime(), row.open, row.high, row.low, row.close)
            for row in frame.itertuples(index=False))
    for bar in shift_bars(bars, BROKER_SERVER_TZ):
        strategy.add_bar(bar)
    strategy.close_live_sessions()

    return sorted(
        (
            pd.Timestamp(p.open_dt),
            "long" if p.is_long else "short",
            p.open_price, p.sl, p.tp,
            _OUTCOMES[p.outcome],
            pd.Timestamp(p.close_dt),
            p.close_price if p.outcome in (Outcome.TP_HIT, Outcome.SL_HIT) else None,
        )
        for session in sessions
        for p in session.create_report().positions
    )


def _port_trades(frame: pd.DataFrame, max_range_pips: float, risk_reward: float) -> list[tuple]:
    data = HistoricalData(frame, SampleSize.Parse("1m"), EurUsd())
    backtest = Backtest(
        SessionBreakout(max_range_pips=max_range_pips, risk_reward=risk_reward),
        data,
        cost_model=FixedCost(pips=0.0),
        ambiguity_policy=AmbiguityPolicy.EXCLUDE,
        position_resolve_delay=PositionCloseDelay.ENTRY_BAR,
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
            open_dt, row.side, row.open_price, row.sl, row.tp, row.outcome, close_dt,
            row.close_price if row.outcome in priced else None,
        )
        for row, open_dt, close_dt in zip(trades.itertuples(index=False), to_utc("open_dt"), to_utc("close_dt"))
    )


def test_reproduces_the_script_trade_for_trade() -> None:
    frame = _random_walk()

    for max_range_pips, risk_reward in [(30.0, 1.5), (15.0, 2.0)]:
        script = _script_trades(frame, max_range_pips, risk_reward)
        port = _port_trades(frame, max_range_pips, risk_reward)

        assert len(script) > 20                                   # the walk actually trades
        assert {t[5] for t in script} >= {"take-profit-hit", "stop-loss-hit", "manual-close"}
        assert port == script
