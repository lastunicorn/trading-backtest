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

Timezone note: bar timestamps are converted from broker-server time (New York
+ 7h, `domain.broker_clock.BROKER_SERVER_TZ`) to UTC as they're read (see
`retrieve_bars`, `domain.bar_approach.shift_bars`), so the GMT+2/GMT+3 offset
applied follows the US daylight-saving dates, as the broker's does. `_SESSION_TEMPLATE` converts its own local start/end
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
from typing import ClassVar, TextIO
from zoneinfo import ZoneInfo
from domain.trading_session_template import AsianSessionTemplate

from domain.bar_approach.daily_session_base import DailySessionBase
from domain.bar_approach.daily_strategy_base import DailyStrategyBase
from domain.bar_approach.position import Outcome, PendingPosition, Position
from domain.bar_approach.shift_bars import shift_bars
from domain.broker_clock import BROKER_SERVER_TZ
from domain.symbol import EurUsd, Symbol
from domain.trading_session import TradingSession
from domain.trading_session_template import TradingSessionTemplate, TokyoSessionTemplate, AsianSessionTemplate
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

_SYMBOL: Symbol = EurUsd()


@dataclass
class SessionBreakoutStrategy(DailyStrategyBase):
    """Encapsulates the Tokyo Session Breakout rules (see
    tokyo-session-breakout.md): decides each day's range-session range (see
    `_SESSION_TEMPLATE`), whether it's tradeable, and simulates the
    breakout/SL/TP/force-close outcome for both sides. See
    `DailyStrategyBase` for the bar-feeding/session-lifecycle contract
    (add_bar, close_live_sessions, on_session_closed)."""

    max_range_pips: float = 30.0
    risk_reward_ratio: float = 1.5

    def _create_session(self, day: _date) -> DailySessionBase:
        return DailySession(day, max_range_pips=self.max_range_pips, risk_reward_ratio=self.risk_reward_ratio)


@dataclass
class DailySession(DailySessionBase):
    """One calendar day's range-session range (see `_SESSION_TEMPLATE`) plus
    the breakout window it opens. Accumulates session-window bars until the
    session's own end time, decides whether the day trades, then simulates
    the breakout/SL/TP outcome for both sides as further bars arrive --
    through its own end_dt (the session's own end time the day after).
    See `DailySessionBase` for the add_bar/close_at/end_dt lifecycle
    contract."""

    # ClassVar, not a field: an annotated class-body assignment on a
    # @dataclass becomes an __init__ parameter unless marked ClassVar,
    # which silently shifts every positional argument after it.
    #_SESSION_TEMPLATE: ClassVar[TradingSessionTemplate] = TokyoSessionTemplate()
    _SESSION_TEMPLATE: ClassVar[TradingSessionTemplate] = AsianSessionTemplate()

    # _SESSION_TEMPLATE: ClassVar[TradingSessionTemplate] = TradingSessionTemplate(
    #     start_time=_time(8, 0, tzinfo=ZoneInfo("America/New_York")),
    #     end_time=_time(9, 0, tzinfo=ZoneInfo("America/New_York")),
    # )

    max_range_pips: float = 10.0
    risk_reward_ratio: float = 1.0
    reference_session: TradingSession = field(init=False, repr=False)

    trading_start_dt: datetime = field(init=False, repr=False)
    trading_end_dt: datetime = field(init=False, repr=False)

    _is_reference_session_resolved: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """`start_dt`/`end_dt`/`trading_start_dt`/`trading_end_dt` are all
        fixed once `day` (and the module-level `_SESSION_TEMPLATE`) are
        known, so they're computed once here rather than recomputed on every
        `add_bar()` call -- they used to be `@property`s that redid a
        `ZoneInfo` conversion on every single bar of the stream."""
        self.reference_session = self._SESSION_TEMPLATE.create_session(self.day)

        # Naive, UTC wall-clock -- matches every other datetime in this class
        # (see module docstring's timezone note); `session.start/end_dt_utc()`
        # are aware. Bars before this are ignored by DailySessionBase.add_bar().
        self.start_dt = self.reference_session.start_dt_utc().replace(tzinfo=None)

        # Force-close point for any position still open: the session's own
        # end time, one calendar day after the session's own day.
        self.end_dt = self._SESSION_TEMPLATE.end_time_utc_on(self.day + timedelta(days=1)).replace(tzinfo=None)

        # Positions are only opened from the reference session's own end
        # time (e.g. London open) through end_dt -- the breakout/force-close
        # window that runs one calendar day past the reference session's own day.
        self.trading_start_dt = self.reference_session.end_dt_utc().replace(tzinfo=None)
        self.trading_end_dt = self.end_dt

    @property
    def range_pips(self) -> float:
        return _SYMBOL.to_pips(self.reference_session.range)

    @property
    def is_cancelled(self) -> bool:
        return self.reference_session.bar_count == 0 or self.range_pips > self.max_range_pips

    # override
    def _process_bar(self, bar: Bar) -> None:
        if not self._is_reference_session_resolved:
            self._add_to_reference_session(bar)
        
        if self._is_reference_session_resolved and self.trading_start_dt <= bar.dt <= self.trading_end_dt:
            self._process_positions(bar)

    def _add_to_reference_session(self, bar: Bar) -> bool:
        if bar.dt.date() == self.day:
            if self.reference_session.add(bar):
                return True

        self._resolve_reference_session()
        return False

    def _resolve_reference_session(self) -> None:
        self._is_reference_session_resolved = True

        if self.is_cancelled:
            return

        mid = self.reference_session.mid

        pending_long = PendingPosition.for_level(self.reference_session.high_value, mid, self.risk_reward_ratio)
        self._pending_positions.append(pending_long)

        pending_short = PendingPosition.for_level(self.reference_session.low_value, mid, self.risk_reward_ratio)
        self._pending_positions.append(pending_short)

    # override
    def _close_all_positions(self, dt: datetime) -> None:
        for position in self._positions:
            if position.is_closed is False:
                position.close(dt)

    def create_report(self) -> DailySessionReport:
        """Snapshot this (closed) session into an immutable `DailySessionReport`
        -- everything a display layer needs, and nothing that requires reaching
        back into this (mutable, possibly still-simulating-other-days) session
        afterwards."""
        bar_block = self.reference_session.bar_block if self.reference_session.bar_count > 0 else None
        positions = [p for p in self._positions if p is not None]

        return DailySessionReport(
            day=self.day,
            name=f"{self.reference_session.start_dt_utc():%H:%M}-{self.reference_session.end_dt_utc():%H:%M} UTC",
            bar_count=self.reference_session.bar_count,
            open_value=bar_block.open_value if bar_block is not None else None,
            open_dt=bar_block.open_dt if bar_block is not None else None,
            high_value=bar_block.high_value if bar_block is not None else None,
            high_dt=bar_block.high_dt if bar_block is not None else None,
            low_value=bar_block.low_value if bar_block is not None else None,
            low_dt=bar_block.low_dt if bar_block is not None else None,
            close_value=bar_block.close_value if bar_block is not None else None,
            close_dt=bar_block.close_dt if bar_block is not None else None,
            range_value=bar_block.range if bar_block is not None else None,
            is_cancelled=self.is_cancelled,
            max_range_pips=self.max_range_pips,
            range_pips=self.range_pips,
            risk_reward_ratio=self.risk_reward_ratio,
            positions=positions,
            first_candle_dt=self.first_candle_dt,
            last_candle_dt=self.last_candle_dt,
        )


def main() -> None:
    start_time = time.perf_counter()

    args = parse_arguments()
    source_path = args.source
    out_dir = Path(args.out)
    
    execute(out_dir, source_path, args.max_range_pips, args.risk_reward)

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

    return parser.parse_args()


@dataclass
class _MonthlyReportWriter:
    """`on_session_closed` callback: writes each closed DailySession's
    day-by-day block to the report file as it arrives, and rolls a
    ReportSummary per calendar month -- the moment a session's day belongs
    to a new (year, month), the previous month's summary is written out and
    a fresh one started. `flush()` writes out whatever month was still open
    once the bar stream ends; sessions arrive in day order (a single
    strategy instance processes the whole stream), so month boundaries are
    only ever crossed forward."""

    risk_reward_ratio: float
    max_range_pips: float
    report_file: TextIO
    say: Callable[[str], None]

    _month_key: tuple[int, int] | None = field(default=None, init=False, repr=False)
    _summary: ReportSummary | None = field(default=None, init=False, repr=False)
    has_any_session: bool = field(default=False, init=False, repr=False)

    def __call__(self, session: DailySession) -> None:
        self.has_any_session = True
        report = session.create_report()
        write_daily_session_report(report, self.report_file)

        month_key = (report.day.year, report.day.month)
        if month_key != self._month_key:
            self.flush()
            self._month_key = month_key
            self._summary = ReportSummary(
                risk_reward_ratio=self.risk_reward_ratio,
                max_range_pips=self.max_range_pips,
            )

        self._summary.add(report)

    def flush(self) -> None:
        if self._summary is not None:
            write_report_summary(self._summary, self.say)
            print(file=self.report_file)
        self._summary = None


def execute(
        report_dir_path : Path,
        source_path: Path,
        max_range_pips : float,
        risk_reward_ratio: float,
    ):

    with open_report_file(report_dir_path) as report_file:
        def say(text: str = "") -> None:
            print(text)
            print(text, file=report_file)

        monthly_reports = _MonthlyReportWriter(
            risk_reward_ratio=risk_reward_ratio,
            max_range_pips=max_range_pips,
            report_file=report_file,
            say=say,
        )

        strategy = SessionBreakoutStrategy(
            max_range_pips=max_range_pips,
            risk_reward_ratio=risk_reward_ratio,
            on_session_closed=monthly_reports,
        )

        for bar in retrieve_bars(source_path):
            strategy.add_bar(bar)

        strategy.close_live_sessions()

        if not monthly_reports.has_any_session:
            raise SystemExit("error: no session bars found in source")

        monthly_reports.flush()

    print(f"\nReport written to: {report_dir_path}")


def open_report_file(report_dir_path: Path):
    report_dir_path.mkdir(parents=True, exist_ok=True)
    report_file_path = report_dir_path / "session_breakout_report.txt"

    if report_file_path.exists():
        print(f"INFO: {report_file_path} already exists and will be overwritten.")

    return report_file_path.open("w", encoding="utf-8")


def retrieve_bars(source_path: Path) -> Iterator[Bar]:
    paths = find_files(source_path, recursive=True)

    if not paths:
        raise SystemExit(f"error: no csv files found at {source_path!r}")

    print(f"Reading {len(paths)} file(s) from {source_path}\n")

    for path in paths:
        bars = iterate_bars(str(path), strict=False)
        bars = shift_bars(bars, BROKER_SERVER_TZ)
        yield from bars


@dataclass(frozen=True)
class DailySessionReport:
    """Everything about one closed DailySession that's needed to display it --
    built once, at close time, by `DailySession.create_report()`, and from
    then on used as a plain, immutable snapshot by both
    `write_daily_session_report` and `ReportSummary.add` instead of either
    reaching back into the (mutable, still-simulating-other-days) domain
    object directly."""

    day: _date
    name: str
    bar_count: int
    open_value: float | None
    open_dt: datetime | None
    high_value: float | None
    high_dt: datetime | None
    low_value: float | None
    low_dt: datetime | None
    close_value: float | None
    close_dt: datetime | None
    range_value: float | None
    is_cancelled: bool
    max_range_pips: float
    range_pips: float
    risk_reward_ratio: float
    positions: list[Position]
    first_candle_dt: datetime | None
    last_candle_dt: datetime | None


@dataclass
class ReportSummary:
    """Aggregated totals for one chunk's sessions, ready for
    `write_report_summary`. Starts out holding only the run's fixed
    parameters; add() folds in one SessionReport at a time as each session
    closes, so by the time a chunk's sessions have all closed this same
    instance already is the finished summary -- no separate
    accumulator/finalize step."""

    risk_reward_ratio: float
    max_range_pips: float
    total_days: int = 0
    cancelled_days: int = 0
    position_count: int = 0
    outcome_counts: dict[Outcome, int] = field(default_factory=lambda: {o: 0 for o in Outcome})
    first_dt: datetime | None = None
    last_dt: datetime | None = None

    def add(self, report: DailySessionReport) -> None:
        if self.total_days == 0:
            self.first_dt = report.first_candle_dt
        self.last_dt = report.last_candle_dt
        self.total_days += 1

        if report.is_cancelled:
            self.cancelled_days += 1
            return

        for position in report.positions:
            self.position_count += 1
            self.outcome_counts[position.outcome] += 1

    @property
    def traded_days(self) -> int:
        return self.total_days - self.cancelled_days

    @property
    def pl_percent(self) -> float:
        return (
            self.outcome_counts[Outcome.TP_HIT] * self.risk_reward_ratio
            - self.outcome_counts[Outcome.SL_HIT]
        )


def write_daily_session_report(report: DailySessionReport, out: TextIO) -> None:
    """Write one session's day-by-day block to `out` only -- no accounting.
    Called once per session, directly from the on_session_closed callback,
    as each session closes; see ReportSummary.add for the totals this used
    to accumulate inline."""
    print(f"=== {report.day.isoformat()} (session {report.name}) ===", file=out)

    if report.bar_count == 0:
        print("  CANCELLED (no session bars for this day)\n", file=out)
        return

    print(f"  Open: {_fmt_price(report.open_value)} ({report.open_dt})", file=out)
    print(f"  High: {_fmt_price(report.high_value)} ({report.high_dt})", file=out)
    print(f"  Low: {_fmt_price(report.low_value)} ({report.low_dt})", file=out)
    print(f"  Close: {_fmt_price(report.close_value)} ({report.close_dt})", file=out)
    print(f"  Range: {_fmt_pips(_SYMBOL.to_pips(report.range_value))}", file=out)

    if report.is_cancelled:
        print(f"  CANCELLED (> {report.max_range_pips:.0f}p threshold)\n", file=out)
        return

    risk_pips = report.range_pips / 2
    print(f"  SL: {_fmt_pips(risk_pips)}   TP: {_fmt_pips(risk_pips * report.risk_reward_ratio)}", file=out)
    if report.positions:
        for position in report.positions:
            label = "LONG " if position.is_long else "SHORT"
            print(_fmt_position(label, position), file=out)
    else:
        print(f"  {outcome_text(Outcome.NONE)}", file=out)
    print(file=out)


def write_report_summary(summary: ReportSummary, say: Callable[[str], None]) -> None:
    say(f"=== summary ({summary.first_dt:%Y-%m-%d %H:%M} -> {summary.last_dt:%Y-%m-%d %H:%M}) ===")
    say(f"  Risk/Reward ratio: {summary.risk_reward_ratio}")
    say(f"  Range sessions: {summary.total_days}   cancelled (range > {summary.max_range_pips:.0f}p): {summary.cancelled_days}")
    say(f"  Eligible days: {summary.traded_days}   positions opened: {summary.position_count}")
    say("  Outcome:")
    for outcome in (Outcome.TP_HIT, Outcome.SL_HIT, Outcome.AMBIGUOUS, Outcome.FORCE_CLOSED):
        say(f"    {outcome.name}: {summary.outcome_counts[outcome]}")
    say(f"  P/L: {summary.pl_percent:.2f} %")


def _fmt_price(value: float) -> str:
    return f"{value:.{_SYMBOL.price_decimals}f}"


def _fmt_pips(value: float) -> str:
    return f"{value:.1f}p"


def _fmt_position(label: str, position: Position) -> str:
    header = (
        f"  {label}: triggered {position.open_dt:%Y-%m-%d %H:%M} @ "
        f"{_fmt_price(position.open_price)}  "
        f"(SL {_fmt_pips(_SYMBOL.to_pips(position.risk_amount))} @ {_fmt_price(position.sl)}, "
        f"TP {_fmt_pips(_SYMBOL.to_pips(position.reward_amount))} @ {_fmt_price(position.tp)})"
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


_OUTCOME_TEXT: dict[Outcome, str] = {
    Outcome.NONE: "not triggered (H/L not broken by 00:00 next day)",
    Outcome.TP_HIT: "TP HIT",
    Outcome.SL_HIT: "SL HIT",
    Outcome.AMBIGUOUS: "AMBIGUOUS (SL and TP both inside one bar)",
    Outcome.FORCE_CLOSED: "OPEN AT FORCE-CLOSE (window ended, no SL/TP hit)",
}


def outcome_text(outcome: Outcome) -> str:
    return _OUTCOME_TEXT[outcome]


if __name__ == "__main__":
    main()
