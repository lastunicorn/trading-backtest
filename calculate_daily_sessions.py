#!/usr/bin/env python3
"""Per-day OHLC values for each intraday trading session.

For every day in the source data this computes, per session:

  * opening value -- open of the first bar in the session window
  * closing value -- close of the last bar in the session window
  * highest value -- max high over the window
  * lowest value  -- min low over the window

The sessions are the standard ones in `domain.trading_session.SESSIONS`
(Tokyo, Asia, London, New York), picked with --session; the FX Asia session
(09:00-18:00 Asia/Tokyo, i.e. 00:00-09:00 UTC) by default. Each is a window in
its own timezone, so DST is resolved per date, and a day is the date the
session opens on in that zone.

Candles come from the mt5_file_access port (`read_frame`), all files read into
one frame, sorted, and deduplicated (`clean_frame`: where two files hold the
same timestamp, the later file wins); `domain.pandas_approach.session_ohlc`
does the rest. The exports carry no timezone: --source-timezone says which
clock their timestamps are on, "broker" (this repo's MT5 broker-server clock,
New York + 7h) by default, or an IANA name such as "America/New_York" for
histdata.com exports.

Output goes to the console; a file report comes later.

Usage:
    python3 calculate_daily_sessions.py                                  # data/eurusd/1min
    python3 calculate_daily_sessions.py data/eurusd/1min/EURUSD_2020_01.csv
    python3 calculate_daily_sessions.py data/eurusd/1min --session London --session "New York"
    python3 calculate_daily_sessions.py path/to/histdata --source-timezone America/New_York
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from datetime import tzinfo
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import pandas as pd

from domain.broker_clock import BROKER_TZ_NAME, timezone_by_name, timezone_name
from domain.pandas_approach.frames import clean_frame
from domain.pandas_approach.session_ohlc import session_ohlc
from domain.trading_session import ASIA_SESSION, SESSIONS, TradingSession
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import read_frame

DEFAULT_SOURCE = "/nfs/YubabaFinance/trading/historical data/arty/eurusd/1min"
DEFAULT_SESSIONS = [ASIA_SESSION.name]
PRICE_DECIMALS = 5


def main() -> int:
    args = _parse_args()

    paths = find_files(args.source)

    if not paths:
        print(f"ERROR: no csv files found at {args.source!r}", file=sys.stderr)
        return 1

    try:
        source_timezone = timezone_by_name(args.source_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"ERROR: unknown --source-timezone {args.source_timezone!r}", file=sys.stderr)
        return 1

    sessions = [SESSIONS[name] for name in args.session or DEFAULT_SESSIONS]

    print(f"Reading {len(paths)} file(s) from {args.source} ({timezone_name(source_timezone)} clock)\n")
    result = collect_sessions(paths, sessions, source_timezone=source_timezone)

    for session in sessions:
        print_session(session, result[session])

    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=DEFAULT_SOURCE,
        help=f"folder of M1 exports, or a single csv file (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--session",
        action="append",
        choices=list(SESSIONS),
        help=f"a session to report; repeat for several (default: {', '.join(DEFAULT_SESSIONS)})",
    )
    parser.add_argument(
        "--source-timezone",
        default=BROKER_TZ_NAME,
        help=f"the clock the exports' timestamps are on: '{BROKER_TZ_NAME}' or an IANA name "
             f"(default: {BROKER_TZ_NAME})",
    )
    return parser.parse_args()


def collect_sessions(
    paths: Iterable[Path], sessions: list[TradingSession], *, source_timezone: tzinfo
) -> dict[TradingSession, pd.DataFrame]:
    """session -> its `session_ohlc` frame (date, open, high, low, close,
    bar_count), one row per day whose session has at least one bar.

    `source_timezone` labels the exports' naive timestamps; nothing is shifted.
    """
    frame = clean_frame(pd.concat([read_frame(str(path), strict=False) for path in paths], ignore_index=True))

    return {session: session_ohlc(frame, session, timezone=source_timezone) for session in sessions}


def window_label(session: TradingSession) -> str:
    """"09:00-18:00 Asia/Tokyo", or each bound with its own zone when they differ."""
    start_zone = timezone_name(session.start_time.tzinfo)
    end_zone = timezone_name(session.end_time.tzinfo)

    if start_zone == end_zone:
        return f"{session.start_time:%H:%M}-{session.end_time:%H:%M} {start_zone}"
    return f"{session.start_time:%H:%M} {start_zone} - {session.end_time:%H:%M} {end_zone}"


def print_session(session: TradingSession, days: pd.DataFrame) -> None:
    width = PRICE_DECIMALS + 3  # "1.12112" fits; leaves room for a leading digit

    def price(value: float) -> str:
        return f"{value:>{width}.{PRICE_DECIMALS}f}"

    print(f"=== {session.name} session ({window_label(session)}, end exclusive) ===")

    if days.empty:
        print("  (no bars in window)\n")
        return

    print(
        f"{'date':<10}  {'open':>{width}}  {'close':>{width}}  "
        f"{'high':>{width}}  {'low':>{width}}  {'bars':>5}"
    )

    for day in days.itertuples(index=False):
        print(
            f"{day.date.isoformat():<10}  {price(day.open)}  {price(day.close)}  "
            f"{price(day.high)}  {price(day.low)}  {day.bar_count:>5}"
        )

    print(f"  {len(days)} session-days\n")


if __name__ == "__main__":
    sys.exit(main())
