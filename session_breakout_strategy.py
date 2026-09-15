"""Backtest of the Tokyo Session Breakout strategy (see tokyo-session-breakout.md).
Originally scoped to the Tokyo session specifically; the range-setting window
is now any `TradingSessionTemplate` -- see `_SESSION_TEMPLATE` below, which
defaults to Tokyo (`TokyoSessionTemplate`) but can be swapped for another
session's hours.

For each calendar day:

  1. The configured session (`_SESSION_TEMPLATE`; defaults to Tokyo,
     00:00-06:30 UTC / 09:00-15:30 JST bell times) sets H (high) and L (low),
     wicks included. If H-L exceeds --max-range-pips, the day is cancelled --
     no trade is evaluated.
  2. From session end until midnight the next day, whichever of H/L is
     broken first opens a trade in that direction. Both may trigger the same
     day (long on the H break, short on the L break, or vice versa) if price
     reverses after the first breakout. Neither breaking by midnight means no
     trade for that side.
  3. SL is the midpoint of [L, H] for every trade. TP is set as a multiple
     of that same risk (entry to SL) via --risk-reward.
  4. Any position still open is force-closed when the next day's analysis
     happens, i.e. at the session's own end time the day after entry.

Entry price is taken as the broken level itself (H for long, L for short),
not the price of the bar that crossed it -- the strategy only specifies the
trigger, not slippage past it. If a single bar's range covers both the SL and
TP price for an open position, which one would have hit first is undecided
from OHLC alone; the outcome is reported as AMBIGUOUS rather than guessed, the
same convention the rest of this repo uses for ambiguous bars.

Timezone note: bar timestamps are converted from US Eastern (the broker's
server time) to UTC as they're read (see `_stream_bars`, `domain.shift_bars`),
via `ZoneInfo("America/New_York")` so the EST/EDT offset applied is correct
for each bar's date. `_SESSION_TEMPLATE` converts its own local start/end
times to UTC the same way (see `TradingSessionTemplate`), so the window edges
are only correct once both conversions have been applied.

The full day-by-day report is written to <--out>/tokyo_breakout_report.txt;
only the summary (one block per month) is echoed to the console.

Usage:
    python3 tokyo_breakout_strategy.py data/eurusd/1min/EURUSD_2020_01.csv
    python3 tokyo_breakout_strategy.py data/eurusd/1min
    python3 tokyo_breakout_strategy.py data/eurusd/1min --out output/tokyo_breakout_output
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date as _date, datetime, time as _time, timedelta
from pathlib import Path
from typing import TextIO
from zoneinfo import ZoneInfo

from domain.bar_chunks import BarChunks
from domain.bar_block import BarBlock
from domain.position import Outcome, PendingPosition, Position
from domain.shift_bars import shift_bars
from domain.trading_session import TradingSession
from domain.trading_session_template import TokyoSessionTemplate, TradingSessionTemplate
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

PIP = 0.0001
PRICE_DECIMALS = 5

#_SESSION_TEMPLATE: TradingSessionTemplate = TokyoSessionTemplate()
# _SESSION_TEMPLATE: TradingSessionTemplate = TradingSessionTemplate(
#     start_time=_time(8, 0, tzinfo=ZoneInfo("America/New_York")),
#     end_time=_time(9, 0, tzinfo=ZoneInfo("America/New_York")),
# )
_SESSION_TEMPLATE: TradingSessionTemplate = TradingSessionTemplate(
    start_time=_time(0, 0, tzinfo=UTC),
    end_time=_time(9, 0, tzinfo=UTC),
)

# The breakout/force-close window always runs exactly one calendar day past
# the range-session's own day: entries are only taken up to midnight the day
# after (`breakout_cutoff`), and any still-open position is force-closed at
# the session's own end time on that same following day (`window_end`).
_TRADE_WINDOW = timedelta(days=1)


def _to_pips(price_diff: float) -> float:
    return price_diff / PIP


_OUTCOME_TEXT: dict[Outcome, str] = {
    Outcome.NONE: "not triggered (H/L not broken by 00:00 next day)",
    Outcome.TP_HIT: "TP HIT",
    Outcome.SL_HIT: "SL HIT",
    Outcome.AMBIGUOUS: "AMBIGUOUS (SL and TP both inside one bar)",
    Outcome.FORCE_CLOSED: "OPEN AT FORCE-CLOSE (window ended, no SL/TP hit)",
}


def outcome_text(outcome: Outcome) -> str:
    return _OUTCOME_TEXT[outcome]


@dataclass
class SessionBreakoutStrategy:
    """Encapsulates the Tokyo Session Breakout rules (see
    tokyo-session-breakout.md): fed one chronological bar at a time via
    add_bar(), decides each day's range-session range (see
    `_SESSION_TEMPLATE`), whether it's tradeable, and simulates the
    breakout/SL/TP/force-close outcome for both sides.

    Each instance is scoped to one chunk of a caller-defined stream split
    (see `domain.bar_chunks`); it doesn't know or care what the chunk
    boundaries are -- that's entirely the caller's business. What it does
    know is its own retirement: while live, add_bar() creates a new
    TbsDailySession the moment a bar for a new calendar day appears. Once
    retire() has been called, add_bar() stops spawning sessions but keeps
    feeding bars to whatever's already live -- so a session whose window
    runs past midnight into the next chunk can still resolve. This lets a
    caller hand the same trailing bars to both the current chunk's instance
    and the previous chunk's (now-retired) instance during the handover: the
    retired instance just drains its lingering live session(s) and, once
    has_live_sessions is False, stops needing bars at all -- it never grows
    a shadow copy of the new chunk's sessions.

    close_live_sessions() force-closes whatever's still live, for use once
    the bar stream truly ends (no next chunk arrives to hand off to)."""

    max_range_pips: float = 30.0
    risk_reward_ratio: float = 1.5

    _sessions: dict[_date, StrategyDailySession] = field(default_factory=dict, init=False, repr=False)
    _session_order: list[_date] = field(default_factory=list, init=False, repr=False)
    _live_sessions: list[StrategyDailySession] = field(default_factory=list, init=False, repr=False)
    _is_retiring: bool = field(default=False, init=False, repr=False)

    @property
    def sessions(self) -> list[StrategyDailySession]:
        """Every session this instance has created, oldest first."""
        return [self._sessions[d] for d in self._session_order]

    @property
    def has_live_sessions(self) -> bool:
        return bool(self._live_sessions)

    def add_bar(self, bar: Bar) -> None:
        """Feed one bar (bars must arrive chronologically). Creates a new
        DailySession the moment a bar for a new calendar day appears, but
        only if that day is in this instance's own chunk -- see class
        docstring. Every currently-live session then receives the bar, so a
        day's own session (accumulating its range-session range) and the
        previous day's session (still resolving its breakout window, which
        runs until the session's own end time the day after) are both fed
        the same bar. A session force-closes itself, and freezes, once a bar
        reaches its window_end; add_bar() only has to notice that and drop
        it from the live list."""
        bar_date = bar.dt.date()

        if bar_date not in self._sessions and not self._is_retiring:
            session = StrategyDailySession(bar_date, self.max_range_pips, self.risk_reward_ratio)
            self._sessions[bar_date] = session
            self._session_order.append(bar_date)
            self._live_sessions.append(session)

        for session in list(self._live_sessions):
            session.add_bar(bar)

            if session.is_closed:
                self._live_sessions.remove(session)

    def retire(self) -> None:
        """Force-close all live sessions and mark this chunk as retired."""
        self._is_retiring = True

    def close_live_sessions(self) -> None:
        """Force-close every still-live session at its own window_end."""
        for session in self._live_sessions:
            session.close(session.window_end)
        self._live_sessions.clear()


@dataclass
class StrategyDailySession:
    """One calendar day's range-session range (see `_SESSION_TEMPLATE`) plus
    the breakout window it opens. Accumulates session-window bars via
    `add_bar()` until the session's own end time, decides whether the day
    trades, then simulates the breakout/SL/TP outcome for both sides as
    further bars arrive -- through its own window_end (the session's own end
    time the day after). `close()` force-closes anything still open and
    freezes the session; calling `add_bar()` or `close()` again afterwards
    raises."""

    day: _date
    max_range_pips: float = 10.0
    risk_reward_ratio: float = 1.0
    session: TradingSession = field(init=False, repr=False)

    session_start: datetime = field(init=False, repr=False)
    window_start: datetime = field(init=False, repr=False)
    window_end: datetime = field(init=False, repr=False)
    breakout_cutoff: datetime = field(init=False, repr=False)

    pending_long: PendingPosition | None = None
    pending_short: PendingPosition | None = None

    position_long: Position | None = None
    position_short: Position | None = None

    _is_session_resolved: bool = field(default=False, init=False, repr=False)
    _is_closed: bool = field(default=False, init=False, repr=False)
    _closed_dt: datetime | None = field(default=None, init=False, repr=False)

    _first_candle_dt: datetime | None = field(default=None, init=False, repr=False)
    _last_candle_dt: datetime | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """`session_start`/`window_start`/`window_end`/`breakout_cutoff` are
        all fixed once `day` (and the module-level `_SESSION_TEMPLATE`) are
        known, so they're computed once here rather than recomputed on every
        `add_bar()` call -- they used to be `@property`s that redid a
        `ZoneInfo` conversion on every single bar of the stream."""
        self.session = _SESSION_TEMPLATE.create_session(self.day)

        # Naive, UTC wall-clock -- matches every other datetime in this class
        # (see module docstring's timezone note); `session.start/end_dt_utc()`
        # are aware.
        self.session_start = self.session.start_dt_utc().replace(tzinfo=None)
        self.window_start = self.session.end_dt_utc().replace(tzinfo=None)

        # Entries are only taken up to midnight `_TRADE_WINDOW` after the
        # session's day -- a break past this point opens no trade.
        self.breakout_cutoff = datetime.combine(self.day + _TRADE_WINDOW, _time(0, 0))

        # Force-close point for any position still open: the session's own
        # end time, `_TRADE_WINDOW` after the session's day.
        self.window_end = _SESSION_TEMPLATE.end_time_utc_on(self.day + _TRADE_WINDOW).replace(tzinfo=None)

    @property
    def range_pips(self) -> float:
        return _to_pips(self.session.range)

    @property
    def is_cancelled(self) -> bool:
        return self.session.bar_count == 0 or self.range_pips > self.max_range_pips

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def closed_dt(self) -> datetime | None:
        return self._closed_dt

    @property
    def first_candle_dt(self) -> datetime | None:
        return self._first_candle_dt

    @property
    def last_candle_dt(self) -> datetime | None:
        return self._last_candle_dt

    def add_bar(self, bar: Bar) -> bool:
        if self._is_closed:
            raise RuntimeError(f"DailySession for {self.day} is already closed at {self.closed_dt}. Cannot add more bars.")

        if self._first_candle_dt is None:
            self._first_candle_dt = bar.dt
        self._last_candle_dt = bar.dt

        if bar.dt >= self.window_end:
            self.close(self.window_end)
            return False

        if not self._is_session_resolved:
            if self._process_bar_session(bar):
                return True

        if bar.dt >= self.window_start:
            self._process_bar_normal(bar)
            return True

        return False

    def _process_bar_session(self, bar: Bar) -> bool:
        if bar.dt < self.session_start:
            return False

        if bar.dt.date() == self.day:
            success = self.session.add(bar)
            if success:
                return True

        self._resolve_session()
        return False

    def _resolve_session(self) -> None:
        self._is_session_resolved = True
        if self.is_cancelled:
            return
        mid = self.session.mid
        self.pending_long = PendingPosition.for_level(self.session.high_value, mid, self.risk_reward_ratio)
        self.pending_short = PendingPosition.for_level(self.session.low_value, mid, self.risk_reward_ratio)

    def _process_bar_normal(self, bar: Bar) -> None:
        self.position_long = self._process_side(bar, self.position_long, self.pending_long)
        self.position_short = self._process_side(bar, self.position_short, self.pending_short)

    def _process_side(
        self, bar: Bar, position: Position | None, pending: PendingPosition | None
    ) -> Position | None:
        if pending is None:
            return None

        if position is None:
            if bar.dt < self.breakout_cutoff:
                position = pending.hit(bar)
                if position is not None:
                    position.hit(bar)
            return position

        if not position.is_closed:
            position.hit(bar)

        return position

    def close_at_end(self) -> bool:
        return self.close(self.window_end)

    def close(self, at: datetime) -> bool:
        if self._is_closed:
            if at !=self.closed_dt:
                raise RuntimeError(f"DailySession for {self.day} is already closed at {self.closed_dt}")
            else:
                return False

        for position in (self.position_long, self.position_short):
            if position is not None and position.is_closed is False:
                position.close(at)

        self._is_closed = True
        self._closed_dt = at

        return True


def main() -> None:
    start_time = time.perf_counter()

    args = parse_arguments()
    source_path = args.source
    out_dir = Path(args.out)
    
    execute(out_dir, source_path, args.max_range_pips, args.risk_reward, args.granularity)

    elapsed = time.perf_counter() - start_time
    print()
    print(f"Execution time: {elapsed:.2f}s")


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "source",
        help="a single M1 csv export, or a folder of them"
    )
    parser.add_argument(
        "--max-range-pips",
        type=float,
        default=30.0,
        help="cancel a day if its range-session range exceeds this many pips (default: 30.0)",
    )
    parser.add_argument(
        "--risk-reward",
        type=float,
        default=1.5,
        help="TP distance as a multiple of the SL distance (default: 1.5)",
    )
    parser.add_argument(
        "--out",
        default="output/session_breakout_output",
        help="directory to write session_breakout_report.txt into (default: output/session_breakout_output)",
    )
    parser.add_argument(
        "--granularity",
        choices=["monthly", "yearly", "none"],
        default="none",
        help="how often to force-close still-live sessions while streaming bars (default: none)",
    )

    return parser.parse_args()


def execute(
        report_dir_path : Path,
        source_path: Path,
        max_range_pips : float,
        risk_reward_ratio: float,
        granularity: str
    ):
    
    with open_report_file(report_dir_path) as report_file:
        def flush(strategy: SessionBreakoutStrategy) -> None:
            strategy.close_live_sessions()
            print_report(strategy.sessions, report_file)
            print(file=report_file)

        all_bars = _retrieve_bars(source_path)
        bar_chunks = BarChunks(all_bars, granularity=granularity)

        previous: SessionBreakoutStrategy | None = None

        while bar_chunks.has_more:
            current = SessionBreakoutStrategy(max_range_pips=max_range_pips, risk_reward_ratio=risk_reward_ratio)

            for bar in bar_chunks.iterate():
                current.add_bar(bar)

                if previous is not None:
                    previous.add_bar(bar)
                    if not previous.has_live_sessions:
                        flush(previous)
                        previous = None

            if previous is not None:
                # Defensive: the previous chunk's sessions outlived this
                # rollover. Shouldn't happen with real M1 data -- a
                # session's window runs at most ~1 day past a chunk boundary
                # -- but don't silently drop it if it ever does.
                flush(previous)

            current.retire()
            previous = current

        if previous is None:
            raise SystemExit("error: no session bars found in source")
        
        flush(previous)

    print(f"\nReport written to: {report_dir_path}")


def open_report_file(report_dir_path: Path):
    report_dir_path.mkdir(parents=True, exist_ok=True)
    report_file_path = report_dir_path / "session_breakout_report.txt"

    if report_file_path.exists():
        print(f"INFO: {report_file_path} already exists and will be overwritten.")

    return report_file_path.open("w", encoding="utf-8")


def _retrieve_bars(source_path: Path) -> Iterator[Bar]:
    paths = find_files(source_path, recursive=True)

    if not paths:
        raise SystemExit(f"error: no csv files found at {source_path!r}")

    print(f"Reading {len(paths)} file(s) from {source_path}\n")

    # Broker server time is US Eastern; ZoneInfo applies the correct
    # EST/EDT offset per bar.
    zone_info = ZoneInfo("America/New_York")

    for path in paths:
        bars = iterate_bars(str(path), strict=False)
        bars = shift_bars(bars, zone_info)
        yield from bars


def _fmt_price(value: float) -> str:
    return f"{value:.{PRICE_DECIMALS}f}"


def _fmt_pips(value: float) -> str:
    return f"{value:.1f}p"


def _fmt_position(label: str, position: Position | None) -> str:
    if position is None:
        return f"  {label}: {outcome_text(Outcome.NONE)}"

    header = (
        f"  {label}: triggered {position.open_dt:%Y-%m-%d %H:%M} @ "
        f"{_fmt_price(position.open_price)}  "
        f"(SL {_fmt_pips(_to_pips(position.risk_amount))} @ {_fmt_price(position.sl)}, "
        f"TP {_fmt_pips(_to_pips(position.reward_amount))} @ {_fmt_price(position.tp)})"
    )

    if not position.is_closed:
        detail = "    -> still open (not yet resolved)"
    elif position.outcome == Outcome.FORCE_CLOSED:
        detail = f"    -> {outcome_text(Outcome.FORCE_CLOSED)} at {position.close_dt:%Y-%m-%d %H:%M}"
    elif position.outcome == Outcome.AMBIGUOUS:
        detail = f"    -> {outcome_text(Outcome.AMBIGUOUS)} at {position.close_dt:%Y-%m-%d %H:%M}"
    else:
        detail = (
            f"    -> {outcome_text(position.outcome)} at {position.close_dt:%Y-%m-%d %H:%M} "
            f"@ {_fmt_price(position.close_price)}"
        )
    return header + "\n" + detail


def print_bar_block(bar_block: BarBlock, indent: str, out: TextIO) -> None:
    print(f"{indent}Open: {_fmt_price(bar_block.open_value)} ({bar_block.open_dt})", file=out)
    print(f"{indent}High: {_fmt_price(bar_block.high_value)} ({bar_block.high_dt})", file=out)
    print(f"{indent}Low: {_fmt_price(bar_block.low_value)} ({bar_block.low_dt})", file=out)
    print(f"{indent}Close: {_fmt_price(bar_block.close_value)} ({bar_block.close_dt})", file=out)
    print(f"{indent}Range: {_fmt_pips(_to_pips(bar_block.range))}", file=out)


@dataclass
class TbsSummary:
    """Aggregated totals for a `print_report` run, ready for `write_summary`."""

    first_dt: datetime
    last_dt: datetime
    risk_reward_ratio: float
    max_range_pips: float
    total_days: int
    cancelled_days: int
    position_count: int
    outcome_counts: dict[Outcome, int]

    @property
    def traded_days(self) -> int:
        return self.total_days - self.cancelled_days

    @property
    def pl_percent(self) -> float:
        return (
            self.outcome_counts[Outcome.TP_HIT] * self.risk_reward_ratio
            - self.outcome_counts[Outcome.SL_HIT]
        )


def write_summary(summary: TbsSummary, say: Callable[[str], None]) -> None:
    say(f"=== summary ({summary.first_dt:%Y-%m-%d %H:%M} -> {summary.last_dt:%Y-%m-%d %H:%M}) ===")
    say(f"  Risk/Reward ratio: {summary.risk_reward_ratio}")
    say(f"  Range sessions: {summary.total_days}   cancelled (range > {summary.max_range_pips:.0f}p): {summary.cancelled_days}")
    say(f"  Eligible days: {summary.traded_days}   positions opened: {summary.position_count}")
    say("  Outcome:")
    for outcome in (Outcome.TP_HIT, Outcome.SL_HIT, Outcome.AMBIGUOUS, Outcome.FORCE_CLOSED):
        say(f"    {outcome.name}: {summary.outcome_counts[outcome]}")
    say(f"  P/L: {summary.pl_percent:.2f} %")


def print_report(results: list[StrategyDailySession], out: TextIO) -> None:
    """Write the full day-by-day report to `out` only. The summary section
    at the end is written to `out` and echoed to the console, since it's the
    only part of the report meant to be read there. The summary title's
    timestamps come from the first candle of the first session and the last
    candle of the last session in `results`."""
    counts = {"cancelled": 0, "no_session": 0, "days": 0}
    outcome_counts: dict[Outcome, int] = {o: 0 for o in Outcome}
    position_count = 0

    for result in results:
        session = result.session
        counts["days"] += 1
        window_label = f"{session.start_dt_utc():%H:%M}-{session.end_dt_utc():%H:%M} UTC"
        print(f"=== {result.day.isoformat()} (session {window_label}) ===", file=out)

        if session.bar_count == 0:
            counts["cancelled"] += 1
            print("  CANCELLED (no session bars for this day)\n", file=out)
            continue

        print_bar_block(session.bars, "  ", out)

        if result.is_cancelled:
            counts["cancelled"] += 1
            print(f"  CANCELLED (> {result.max_range_pips:.0f}p threshold)\n", file=out)
            continue

        risk_pips = result.range_pips / 2
        print(f"  SL: {_fmt_pips(risk_pips)}   TP: {_fmt_pips(risk_pips * result.risk_reward_ratio)}", file=out)
        print(_fmt_position("LONG ", result.position_long), file=out)
        print(_fmt_position("SHORT", result.position_short), file=out)
        print(file=out)

        for position in (result.position_long, result.position_short):
            if position is not None:
                position_count += 1
                outcome_counts[position.outcome] += 1

    def say(text: str = "") -> None:
        print(text)
        print(text, file=out)

    summary = TbsSummary(
        first_dt=results[0].first_candle_dt,
        last_dt=results[-1].last_candle_dt,
        risk_reward_ratio=results[0].risk_reward_ratio,
        max_range_pips=results[0].max_range_pips,
        total_days=counts["days"],
        cancelled_days=counts["cancelled"],
        position_count=position_count,
        outcome_counts=outcome_counts,
    )
    write_summary(summary, say)


if __name__ == "__main__":
    main()
