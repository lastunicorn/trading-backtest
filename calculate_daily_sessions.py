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

Candles are read by the loader for --source-format, the same one backtest.py
picks from its config's `data_source.format` (`application.load_source`):
"metatrader" (this repo's MT5 exports, the default), "histdata" (histdata.com
MetaTrader downloads) or "dukascopy" (bid/ask pairs). Every file is read into
one frame, sorted and deduplicated (where two files hold the same timestamp,
the later file wins); `domain.pandas_approach.session_ohlc` does the rest. The
exports carry no timezone: --source-timezone says which clock their timestamps
are on, "broker" (this repo's MT5 broker-server clock, New York + 7h) by
default, or an IANA name. It is never inferred from the format, but histdata
must be "America/New_York" and Dukascopy "UTC": any other clock is an error.
--symbol (EURUSD by default) sets the price decimals printed.

Output goes to the console; a file report comes later.

Usage:
    python3 calculate_daily_sessions.py                                  # data/eurusd/1min
    python3 calculate_daily_sessions.py data/eurusd/1min/EURUSD_2020_01.csv
    python3 calculate_daily_sessions.py data/eurusd/1min --session London --session "New York"
    python3 calculate_daily_sessions.py path/to/histdata --source-format histdata --source-timezone America/New_York
    python3 calculate_daily_sessions.py path/to/dukascopy --source-format dukascopy --source-timezone UTC
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import tzinfo
from pathlib import Path
from zoneinfo import ZoneInfoNotFoundError

import pandas as pd

from application.load_historical_data_use_case import SourceFormat, load_source
from domain.broker_clock import BROKER_TZ_NAME, timezone_by_name, timezone_name
from domain.pandas_approach.session_ohlc import session_ohlc
from domain.sample_size import SampleSize
from domain.symbol import EURUSD, Symbol, by_ticker
from domain.trading_session import ASIA_SESSION, SESSIONS, TradingSession

DEFAULT_SOURCE = "/nfs/YubabaFinance/trading/historical data/arty/eurusd/1min"
DEFAULT_SOURCE_FORMAT = SourceFormat.METATRADER
DEFAULT_SESSIONS = [ASIA_SESSION.name]
# The loaders resample to a timeframe; at the sources' own M1 that is a no-op.
SOURCE_TIMEFRAME = SampleSize.Parse("1m")


def main() -> int:
    args = _parse_args()

    try:
        source_timezone = timezone_by_name(args.source_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"ERROR: unknown --source-timezone {args.source_timezone!r}", file=sys.stderr)
        return 1

    try:
        symbol = by_ticker(args.symbol)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    source_format = SourceFormat(args.source_format)
    sessions = [SESSIONS[name] for name in args.session or DEFAULT_SESSIONS]

    print(f"Reading {args.source} ({source_format.value}, {timezone_name(source_timezone)} clock)")
    try:
        result = collect_sessions(args.source, source_format, sessions, symbol=symbol,
                                  source_timezone=source_timezone, progress=print)
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        # Wrong clock for the format, no source files, nothing readable:
        # say so plainly, not as a traceback.
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print()

    for session in sessions:
        print_session(session, result[session], price_decimals=symbol.price_decimals)

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
        "--source-format",
        default=DEFAULT_SOURCE_FORMAT.value,
        choices=[source_format.value for source_format in SourceFormat],
        help=f"how the exports are laid out, which picks the reader (default: {DEFAULT_SOURCE_FORMAT.value})",
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
    parser.add_argument(
        "--symbol",
        default=EURUSD.ticker,
        help=f"the exports' symbol, which sets the price decimals (default: {EURUSD.ticker})",
    )
    return parser.parse_args()


def collect_sessions(
    source: str | Path,
    source_format: SourceFormat,
    sessions: list[TradingSession],
    *,
    symbol: Symbol = EURUSD,
    source_timezone: tzinfo,
    progress: Callable[[str], None] | None = None,
) -> dict[TradingSession, pd.DataFrame]:
    """session -> its `session_ohlc` frame (date, open, high, low, close,
    bar_count), one row per day whose session has at least one bar.

    `source` (a folder or one file) is read by `source_format`'s loader.
    `source_timezone` labels the exports' naive timestamps; nothing is shifted.
    The loader raises `ValueError` for a clock its format can't be on, and
    `FileNotFoundError`/`RuntimeError` when there is nothing to read.
    """
    data = load_source(source, source_format, SOURCE_TIMEFRAME, symbol,
                       timezone=source_timezone, progress=progress)

    return {session: session_ohlc(data.data, session, timezone=data.timezone) for session in sessions}


def window_label(session: TradingSession) -> str:
    """"09:00-18:00 Asia/Tokyo", or each bound with its own zone when they differ."""
    start_zone = timezone_name(session.start_time.tzinfo)
    end_zone = timezone_name(session.end_time.tzinfo)

    if start_zone == end_zone:
        return f"{session.start_time:%H:%M}-{session.end_time:%H:%M} {start_zone}"
    return f"{session.start_time:%H:%M} {start_zone} - {session.end_time:%H:%M} {end_zone}"


def print_session(session: TradingSession, days: pd.DataFrame, *, price_decimals: int) -> None:
    print(f"=== {session.name} session ({window_label(session)}, end exclusive) ===")

    if days.empty:
        print("  (no bars in window)\n")
        return

    width = len(f"{days['high'].max():.{price_decimals}f}")   # the widest price fits

    def price(value: float) -> str:
        return f"{value:>{width}.{price_decimals}f}"

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
