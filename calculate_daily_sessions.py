#!/usr/bin/env python3
"""Per-day OHLC values for each intraday trading session.

For every day in the source data this computes, per session:

  * opening value -- open of the first bar in the session window
  * closing value -- close of the last bar in the session window
  * highest value -- max high over the window
  * lowest value  -- min low over the window

The sessions are the standard ones in `domain.trading_session_template.SESSIONS`
(Tokyo, Asia, London, New York), picked with --session; the FX Asia session
(09:00-18:00 Asia/Tokyo, i.e. 00:00-09:00 UTC) by default. Each is a window in
its own timezone, so DST is resolved per date, and a day is the date the
session opens on in that zone.

Candles come from the mt5_file_access port (`iterate_bars`), streamed so a
multi-year folder of M1 exports stays within flat memory. The exports carry no
timezone: --source-timezone says which clock their timestamps are on, "broker"
(this repo's MT5 broker-server clock, New York + 7h) by default, or an IANA
name such as "America/New_York" for histdata.com exports.

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
from dataclasses import replace
from datetime import UTC, date as _date, timedelta, tzinfo
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

from domain.broker_clock import BROKER_TZ_NAME, timezone_by_name, timezone_name
from domain.trading_session import TradingSession
from domain.trading_session_template import ASIA_SESSION, SESSIONS, TradingSessionTemplate
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

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

    templates = [SESSIONS[name] for name in args.session or DEFAULT_SESSIONS]

    print(f"Reading {len(paths)} file(s) from {args.source} ({timezone_name(source_timezone)} clock)\n")
    result = collect_sessions(paths, templates, source_timezone=source_timezone)

    for template in templates:
        print_session(template, result[template])

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
    paths: Iterable[Path], templates: list[TradingSessionTemplate], *, source_timezone: tzinfo
) -> dict[TradingSessionTemplate, dict[_date, TradingSession]]:
    """template -> {date the session opens -> that day's `TradingSession`},
    for every day whose session has at least one bar.

    `source_timezone` labels the exports' naive timestamps; nothing is shifted.
    """
    result: dict[TradingSessionTemplate, dict[_date, TradingSession]] = {t: {} for t in templates}

    for path in paths:
        for bar in iterate_bars(str(path), strict=False):
            # Once per bar, to UTC: every session compares in UTC, and a
            # ShiftedZone (the broker clock) is slow to convert from.
            bar = replace(bar, dt=bar.dt.replace(tzinfo=source_timezone).astimezone(UTC))

            for template in templates:
                _add_to_session(result[template], template, bar)

    return {
        template: {day: session for day, session in days.items() if session.bar_count}
        for template, days in result.items()
    }


def _add_to_session(days: dict[_date, TradingSession], template: TradingSessionTemplate, bar: Bar) -> None:
    """Add `bar` to the session it falls in, if any: the one opening on the
    bar's date in the session's zone, or the day before for a session that
    wraps past midnight. Each day's session is created the first time a bar
    could belong to it."""
    day = bar.dt.astimezone(template.start_time.tzinfo).date()

    for candidate in (day, day - timedelta(days=1)):
        session = days.get(candidate)
        if session is None:
            session = days[candidate] = template.create_session(candidate)
        if session.add(bar):
            return


def window_label(template: TradingSessionTemplate) -> str:
    """"09:00-18:00 Asia/Tokyo", or each bound with its own zone when they differ."""
    start_zone = timezone_name(template.start_time.tzinfo)
    end_zone = timezone_name(template.end_time.tzinfo)

    if start_zone == end_zone:
        return f"{template.start_time:%H:%M}-{template.end_time:%H:%M} {start_zone}"
    return f"{template.start_time:%H:%M} {start_zone} - {template.end_time:%H:%M} {end_zone}"


def print_session(template: TradingSessionTemplate, days: dict[_date, TradingSession]) -> None:
    width = PRICE_DECIMALS + 3  # "1.12112" fits; leaves room for a leading digit

    def price(value: float) -> str:
        return f"{value:>{width}.{PRICE_DECIMALS}f}"

    print(f"=== {template.name} session ({window_label(template)}, end exclusive) ===")

    if not days:
        print("  (no bars in window)\n")
        return

    print(
        f"{'date':<10}  {'open':>{width}}  {'close':>{width}}  "
        f"{'high':>{width}}  {'low':>{width}}  {'bars':>5}"
    )

    for day in sorted(days):
        block = days[day].bar_block
        print(
            f"{day.isoformat():<10}  {price(block.open_value)}  {price(block.close_value)}  "
            f"{price(block.high_value)}  {price(block.low_value)}  {block.bar_count:>5}"
        )

    print(f"  {len(days)} session-days\n")


if __name__ == "__main__":
    sys.exit(main())
