"""Backtest of the Tokyo Session Breakout strategy (see tokyo-session-breakout.md).

For each calendar day:

  1. Tokyo session (00:00-09:00) sets H (high) and L (low), wicks included.
     If H-L > 30 pips, the day is cancelled -- no trade is evaluated.
  2. From session end (09:00) until 00:00 the next day, whichever of H/L is
     broken first opens a trade in that direction. Both may trigger the same
     day (long on the H break, short on the L break, or vice versa) if price
     reverses after the first breakout. Neither breaking by 00:00 means no
     trade for that side.
  3. SL is the midpoint of [L, H] for every trade. TP is set for a 1:2 risk
     /reward from that same risk (entry to SL).
  4. Any position still open is force-closed when the next day's analysis
     happens, i.e. at 09:00 the day after entry.

Entry price is taken as the broken level itself (H for long, L for short),
not the price of the bar that crossed it -- the strategy only specifies the
trigger, not slippage past it. If a single bar's range covers both the SL and
TP price for an open position, which one would have hit first is undecided
from OHLC alone; the outcome is reported as AMBIGUOUS rather than guessed, the
same convention the rest of this repo uses for ambiguous bars.

Timezone note: bar timestamps are shifted 5 hours earlier as they're read (see
`_stream_bars`, `domain.shift_bars`) to convert the exports' broker-server time
to UTC. The task specifies the Tokyo window as 00:00-09:00 UTC, so the window
edges are only correct once that shift has been applied.

Usage:
    python3 tokyo_breakout_strategy.py data/eurusd/1min/EURUSD_2020_01.csv
    python3 tokyo_breakout_strategy.py data/eurusd/1min
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date as _date, datetime, time as _time, timedelta
from pathlib import Path

from domain.bar_block import BarBlock
from domain.position import Outcome, PendingPosition, Position
from domain.shift_bars import shift_bars
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

PIP = 0.0001
PRICE_DECIMALS = 5


def to_pips(price_diff: float) -> float:
    return price_diff / PIP


def _range_pips(bar_block: BarBlock) -> float:
    return to_pips(bar_block.range)


_OUTCOME_TEXT: dict[Outcome, str] = {
    Outcome.NONE: "not triggered (H/L not broken by 00:00 next day)",
    Outcome.TP_HIT: "TP HIT",
    Outcome.SL_HIT: "SL HIT",
    Outcome.AMBIGUOUS: "AMBIGUOUS (SL and TP both inside one bar)",
    Outcome.FORCE_CLOSED: "OPEN AT FORCE-CLOSE (09:00 next day, no SL/TP hit)",
}


def outcome_text(outcome: Outcome) -> str:
    return _OUTCOME_TEXT[outcome]


@dataclass
class TbsDailySession:
    """One calendar day's Tokyo range plus the breakout window it opens.
    Accumulates Tokyo bars via `add_bar()` until 09:00, decides whether the
    day trades, then simulates the breakout/SL/TP outcome for both sides as
    further bars arrive -- through its own window_end (09:00 the day after).
    `close()` force-closes anything still open and freezes the session;
    calling `add_bar()` or `close()` again afterwards raises."""

    TOKYO_START = _time(0, 0)
    TOKYO_END = _time(9, 0)  # exclusive

    day: _date
    max_range_pips: float = 10.0
    risk_reward_ratio: float = 1.0
    tokyo_session: BarBlock = field(default_factory=BarBlock)

    pending_long: PendingPosition | None = None
    pending_short: PendingPosition | None = None

    position_long: Position | None = None
    position_short: Position | None = None

    _is_tokyo_resolved: bool = field(default=False, init=False, repr=False)
    _is_closed: bool = field(default=False, init=False, repr=False)
    _closed_dt: datetime | None = field(default=None, init=False, repr=False)

    @property
    def window_start(self) -> datetime:
        return datetime.combine(self.day, self.TOKYO_END)

    @property
    def breakout_cutoff(self) -> datetime:
        return datetime.combine(self.day + timedelta(days=1), _time(0, 0))

    @property
    def window_end(self) -> datetime:
        return datetime.combine(self.day + timedelta(days=1), self.TOKYO_END)

    @property
    def range_pips(self) -> float:
        return _range_pips(self.tokyo_session)

    @property
    def is_cancelled(self) -> bool:
        return self.tokyo_session.bar_count == 0 or self.range_pips > self.max_range_pips

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def closed_dt(self) -> datetime | None:
        return self._closed_dt

    def add_bar(self, bar: Bar) -> bool:
        if self._is_closed:
            raise RuntimeError(f"DailySession for {self.day} is closed; cannot add more bars")

        if bar.dt >= self.window_end:
            self.close(self.window_end)
            return False

        if not self._is_tokyo_resolved:
            if self._process_bar_tokyo(bar):
                return True

        if bar.dt >= self.window_start:
            self._process_bar_normal(bar)
            return True

        return False

    def _process_bar_tokyo(self, bar: Bar) -> bool:
        t = bar.dt.time()

        if bar.dt.date() == self.day and self.TOKYO_START <= t < self.TOKYO_END:
            self.tokyo_session.add(bar)
            return True

        self._resolve_tokyo()
        return False

    def _resolve_tokyo(self) -> None:
        self._is_tokyo_resolved = True
        if self.is_cancelled:
            return
        mid = self.tokyo_session.mid
        self.pending_long = PendingPosition.for_level(self.tokyo_session.high_value, mid, self.risk_reward_ratio)
        self.pending_short = PendingPosition.for_level(self.tokyo_session.low_value, mid, self.risk_reward_ratio)

    def _process_bar_normal(self, bar: Bar) -> None:
        session = self.tokyo_session
        self.position_long = self._process_side(bar, self.position_long, self.pending_long, True, bar.high > session.high_value)
        self.position_short = self._process_side(bar, self.position_short, self.pending_short, False, bar.low < session.low_value)

    def _process_side(
        self, bar: Bar, position: Position | None, pending: PendingPosition | None, is_long: bool, breaks_level: bool
    ) -> Position | None:
        if pending is None:
            return None
        if position is None:
            if bar.dt < self.breakout_cutoff and breaks_level:
                position = pending.open_position(bar.dt)
                self._check_resolution(position, bar, is_long)
            return position
        if position.close_dt is None:
            self._check_resolution(position, bar, is_long)
        return position

    def _check_resolution(self, position: Position, bar: Bar, is_long: bool) -> None:
        """Update `position` if this bar's range touches its SL and/or TP."""
        if position.tp is None or position.sl is None:
            return
        if is_long:
            hit_tp = bar.high >= position.tp
            hit_sl = bar.low <= position.sl
        else:
            hit_tp = bar.low <= position.tp
            hit_sl = bar.high >= position.sl

        if hit_tp and hit_sl:
            position.outcome = Outcome.AMBIGUOUS
            position.close_dt = bar.dt
        elif hit_tp:
            position.outcome = Outcome.TP_HIT
            position.close_dt = bar.dt
            position.close_price = position.tp
        elif hit_sl:
            position.outcome = Outcome.SL_HIT
            position.close_dt = bar.dt
            position.close_price = position.sl

    def close(self) -> bool:
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


@dataclass
class TokyoBreakoutStrategy:
    """Encapsulates the Tokyo Session Breakout rules (see
    tokyo-session-breakout.md): given one chronological stream of Bars,
    decides each day's Tokyo range, whether it's tradeable, and simulates
    the breakout/SL/TP/force-close outcome for both sides.

    `calculate()` consumes its `bars` argument exactly once."""

    max_range_pips: float = 30.0
    risk_reward: float = 1.5

    def calculate(self, bars: Iterable[Bar]) -> list[TbsDailySession]:
        """One pass over `bars` (must be chronological). A new DailySession
        is created the moment a bar for a new calendar day appears. Every
        currently-live session -- one that hasn't closed itself yet --
        receives the bar via add_bar(), so a day's own session (accumulating
        its Tokyo range) and the previous day's session (still resolving its
        breakout window, which runs until 09:00 the day after) are both fed
        the same bar. add_bar() force-closes the session itself, and freezes
        it, once a bar reaches its window_end; calculate() only has to notice
        that and drop it from the live list."""
        sessions: dict[_date, TbsDailySession] = {}
        session_order: list[_date] = []
        live_sessions: list[TbsDailySession] = []

        for bar in bars:
            bar_date = bar.dt.date()

            if bar_date not in sessions:
                session = TbsDailySession(bar_date, self.max_range_pips, self.risk_reward)
                sessions[bar_date] = session
                session_order.append(bar_date)
                live_sessions.append(session)

            for session in list(live_sessions):
                session.add_bar(bar)

                if session.is_closed:
                    live_sessions.remove(session)

        for session in live_sessions:
            session.close(session.window_end)

        return [sessions[d] for d in session_order]


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
        f"(SL {_fmt_pips(to_pips(position.risk_amount))} @ {_fmt_price(position.sl)}, "
        f"TP {_fmt_pips(to_pips(position.reward_amount))} @ {_fmt_price(position.tp)})"
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


def print_bar_block(bar_block: BarBlock, indent: str) -> None:
    print(f"{indent}Open: {_fmt_price(bar_block.open_value)} ({bar_block.open_dt})")
    print(f"{indent}High: {_fmt_price(bar_block.high_value)} ({bar_block.high_dt})")
    print(f"{indent}Low: {_fmt_price(bar_block.low_value)} ({bar_block.low_dt})")
    print(f"{indent}Close: {_fmt_price(bar_block.close_value)} ({bar_block.close_dt})")
    print(f"{indent}Range: {_fmt_pips(_range_pips(bar_block))}")


def print_report(results: list[TbsDailySession]) -> None:
    counts = {"cancelled": 0, "no_session": 0, "days": 0}
    outcome_counts: dict[Outcome, int] = {o: 0 for o in Outcome}
    triggered_sides = 0

    for result in results:
        session = result.tokyo_session
        counts["days"] += 1
        print(f"=== {result.day.isoformat()} (Tokyo 00:00-09:00) ===")

        if session.bar_count == 0:
            counts["cancelled"] += 1
            print("  CANCELLED (no Tokyo-session bars for this day)\n")
            continue

        print_bar_block(session, "  ")

        if result.is_cancelled:
            counts["cancelled"] += 1
            print(f"  CANCELLED (> {result.max_range_pips:.0f}p threshold)\n")
            continue

        risk_pips = result.range_pips / 2
        print(f"  SL: {_fmt_pips(risk_pips)}   TP: {_fmt_pips(risk_pips * result.risk_reward_ratio)}")
        print(_fmt_position("LONG ", result.position_long))
        print(_fmt_position("SHORT", result.position_short))
        print()

        for position in (result.position_long, result.position_short):
            if position is not None:
                triggered_sides += 1
                outcome_counts[position.outcome] += 1

    total = counts["days"]
    traded_days = total - counts["cancelled"]
    print("=== summary ===")
    print(f"  Tokyo sessions: {total}   cancelled (range > {results[0].max_range_pips:.0f}p): {counts['cancelled']}")
    print(f"  Eligible days: {traded_days}   sides triggered: {triggered_sides}")
    risk_reward_ratio = results[0].risk_reward_ratio
    print(f"  Risk/Reward ratio: {risk_reward_ratio}")
    for outcome in (Outcome.TP_HIT, Outcome.SL_HIT, Outcome.AMBIGUOUS, Outcome.FORCE_CLOSED):
        print(f"    {outcome.name}: {outcome_counts[outcome]}")
    PL = outcome_counts[Outcome.TP_HIT] * risk_reward_ratio - outcome_counts[Outcome.SL_HIT]
    print(f"  P/L: {PL:.2f} %")


def retrieve_bars(source_path):
    paths = find_files(source_path, recursive=True)
    if not paths:
        raise SystemExit(f"error: no csv files found at {source_path!r}")

    print(f"Reading {len(paths)} file(s) from {source_path}\n")

    return _stream_bars(paths)


def _stream_bars(paths: Iterable[Path]) -> Iterator[Bar]:
    def _raw() -> Iterator[Bar]:
        for path in paths:
            yield from iterate_bars(str(path), strict=False)

    return shift_bars(_raw(), timedelta(hours=4))


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", help="a single M1 csv export, or a folder of them")
    parser.add_argument(
        "--max-range-pips", type=float, default=30.0,
        help="cancel a day if its Tokyo range exceeds this many pips (default: 30.0)",
    )
    parser.add_argument(
        "--risk-reward", type=float, default=1.5,
        help="TP distance as a multiple of the SL distance (default: 1.5)",
    )
    return parser.parse_args()


def main() -> None:
    start_time = time.perf_counter()

    args = parse_arguments()

    source_path = args.source
    bars = retrieve_bars(source_path)

    strategy = TokyoBreakoutStrategy(max_range_pips=args.max_range_pips, risk_reward=args.risk_reward)
    results = strategy.calculate(bars)

    if not results:
        raise SystemExit("error: no Tokyo-session bars found in source")

    print_report(results)

    elapsed = time.perf_counter() - start_time
    print(f"\nExecution time: {elapsed:.2f}s")


if __name__ == "__main__":
    main()
