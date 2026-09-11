#!/usr/bin/env python3
"""Per-day OHLC values for each intraday trading session.

For every calendar day in the source data this computes, per session:

  * opening value -- open of the first bar in the session window
  * closing value -- close of the last bar in the session window
  * highest value -- max high over the window
  * lowest value  -- min low over the window

Only the Tokyo session (00:00-09:00, end exclusive) is enabled for now. London
and New York plug into the same machinery: add a `Session` to `SESSIONS`.

Candles come from the mt5_file_access port (`iter_bars`), streamed so a
multi-year folder of M1 exports stays within flat memory.

Timezone note: bar timestamps are used exactly as the exports carry them, and
the session window is applied in that same clock. The task specifies the Tokyo
window as 00:00-09:00 UTC; the rest of this repo's pipeline treats these stamps
as broker-server time. If the two differ, the window edges shift accordingly --
nothing here converts timezones.

Output goes to the console; a file report comes later.

Usage:
    python3 trading_sessions.py                                  # data/eurusd/1min
    python3 trading_sessions.py data/eurusd/1min/EURUSD_2020_01.csv
    python3 trading_sessions.py path/to/folder
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date as _date, datetime, time as _time

from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

DEFAULT_SOURCE = "data/eurusd/1min"
PRICE_DECIMALS = 5


@dataclass(frozen=True, slots=True)
class TradingSession:
    """A named intraday window, [start, end) in the bars' own clock."""

    name: str
    start_time: _time
    end_time: _time  # exclusive

    def contains(self, t: _time) -> bool:
        return self.start_time <= t < self.end_time

    @property
    def window_label(self) -> str:
        return f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"


# London and New York follow the same shape once Tokyo is verified.
TRADING_SESSIONS = [
    TradingSession("Tokyo", _time(0, 0), _time(9, 0)),
]


@dataclass
class SessionDay:
    """One session's OHLC for one date, accumulated as bars stream in.

    Order-independent: `add` compares timestamps rather than assuming the bars
    arrive sorted, so a folder whose files overlap at the edges still yields the
    right open/close.
    """

    open_dt: datetime | None = None
    open: float = 0.0
    close_dt: datetime | None = None
    close: float = 0.0
    high: float = float("-inf")
    low: float = float("inf")
    bars: int = 0

    def add(self, bar: Bar) -> None:
        if self.open_dt is None or bar.dt < self.open_dt:
            self.open_dt, self.open = bar.dt, bar.open
        if self.close_dt is None or bar.dt > self.close_dt:
            self.close_dt, self.close = bar.dt, bar.close
        if bar.high > self.high:
            self.high = bar.high
        if bar.low < self.low:
            self.low = bar.low
        self.bars += 1


def collect_sessions(
    paths, sessions: list[TradingSession]
) -> dict[str, dict[_date, SessionDay]]:
    """session name -> {date -> SessionDay} for every bar that falls in a window."""
    result: dict[str, dict[_date, SessionDay]] = {s.name: {} for s in sessions}

    for path in paths:
        for bar in iterate_bars(str(path), strict=False):
            t = bar.dt.time()

            for session in sessions:
                if session.contains(t):
                    day = result[session.name].setdefault(bar.dt.date(), SessionDay())
                    day.add(bar)

    return result


def print_session(session: TradingSession, days: dict[_date, SessionDay]) -> None:
    width = PRICE_DECIMALS + 3  # "1.12112" fits; leaves room for a leading digit

    def price(value: float) -> str:
        return f"{value:>{width}.{PRICE_DECIMALS}f}"

    print(f"=== {session.name} session ({session.window_label}, end exclusive) ===")

    if not days:
        print("  (no bars in window)\n")
        return

    print(
        f"{'date':<10}  {'open':>{width}}  {'close':>{width}}  "
        f"{'high':>{width}}  {'low':>{width}}  {'bars':>5}"
    )

    for d in sorted(days):
        v = days[d]
        print(
            f"{d.isoformat():<10}  {price(v.open)}  {price(v.close)}  "
            f"{price(v.high)}  {price(v.low)}  {v.bars:>5}"
        )

    print(f"  {len(days)} session-days\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=DEFAULT_SOURCE,
        help=f"folder of M1 exports, or a single csv file (default: {DEFAULT_SOURCE})",
    )
    args = parser.parse_args()

    paths = find_files(args.source)

    if not paths:
        parser.error(f"no csv files found at {args.source!r}")

    print(f"Reading {len(paths)} file(s) from {args.source}\n")
    result = collect_sessions(paths, TRADING_SESSIONS)

    for session in TRADING_SESSIONS:
        print_session(session, result[session.name])


if __name__ == "__main__":
    main()
