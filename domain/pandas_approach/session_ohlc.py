"""Per-day open/high/low/close of a trading session, from a bar frame.

The pandas counterpart to filling one
`domain.trading_session_instance.TradingSessionInstance` per day bar by bar:
every bar is assigned to the session day it falls in, then each day's bars
collapse into one OHLC row.

    from domain.broker_clock import BROKER_SERVER_TZ
    from domain.pandas_approach.session_ohlc import session_ohlc
    from domain.trading_session import ASIA_SESSION

    asia = session_ohlc(m1, ASIA_SESSION, timezone=BROKER_SERVER_TZ)
    # date | open | high | low | close | bar_count

A session day is the date the session opens on in its start zone, so DST is
resolved per date and a session past midnight belongs to the day it opens. The
windows themselves come from `TradingSession.create_session`, once per
date, so this module and the bar approach share one definition of them.
"""

from __future__ import annotations

from datetime import UTC, tzinfo

import pandas as pd

from domain.pandas_approach.shift_timezone import shift_timezone
from domain.trading_session import TradingSession

__all__ = ["SESSION_OHLC_COLUMNS", "session_ohlc"]

SESSION_OHLC_COLUMNS = ["date", "open", "high", "low", "close", "bar_count"]

_ONE_DAY = pd.Timedelta(days=1)


def session_ohlc(frame: pd.DataFrame, session: TradingSession, *, timezone: tzinfo) -> pd.DataFrame:
    """One row per session day with at least one bar, oldest first.

    `frame` needs a naive `datetime` column and float `open`/`high`/`low`/
    `close`; `timezone` is the clock its timestamps are on (it labels them,
    nothing is shifted). Rows need not be sorted. `date` holds `datetime.date`s.
    """
    if frame.empty:
        return pd.DataFrame(columns=SESSION_OHLC_COLUMNS)

    frame = frame.sort_values("datetime", kind="stable")
    utc = shift_timezone(frame, UTC, from_tz=timezone)["datetime"]
    day = _session_day(utc, shift_timezone(frame, session.start_time.tzinfo, from_tz=timezone)["datetime"], session)

    result = frame.groupby(day).agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        bar_count=("open", "size"),
    )
    result.index = result.index.date
    return result.rename_axis("date").reset_index()


def _session_day(utc: pd.Series, start_zone_wall: pd.Series, session: TradingSession) -> pd.Series:
    """Each bar's session day, NaT for a bar outside every session.

    The session holding a bar, if any, opened on the bar's date in the start
    zone or, when it wraps past midnight, the day before -- the same rule as
    `domain.time_window.TimeWindow.contains`.
    """
    today = start_zone_wall.dt.normalize()
    yesterday = today - _ONE_DAY
    starts, ends = _windows(pd.concat([today, yesterday]).unique(), session)

    day = pd.Series(pd.NaT, index=utc.index, dtype=today.dtype)
    for candidate in (yesterday, today):   # today last: it wins where both hold
        inside = (utc >= candidate.map(starts)) & (utc < candidate.map(ends))
        day = day.mask(inside, candidate)
    return day


def _windows(days, session: TradingSession) -> tuple[pd.Series, pd.Series]:
    """Each day's session start and end, as naive UTC, indexed by the day."""
    instances = [session.create_session(day.date()) for day in days]
    index = pd.DatetimeIndex(days)
    starts = pd.Series([s.start_dt_utc().replace(tzinfo=None) for s in instances], index=index)
    ends = pd.Series([s.end_dt_utc().replace(tzinfo=None) for s in instances], index=index)
    return starts, ends
