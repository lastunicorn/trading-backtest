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

TOKYO_START = _time(0, 0)
TOKYO_END = _time(9, 0)  # exclusive
MAX_RANGE_PIPS = 30.0
RISK_REWARD = 1.5


def to_pips(price_diff: float) -> float:
    return price_diff / PIP


_OUTCOME_TEXT: dict[Outcome, str] = {
    Outcome.NONE: "not triggered (H/L not broken by 00:00 next day)",
    Outcome.TP_HIT: "TP HIT",
    Outcome.SL_HIT: "SL HIT",
    Outcome.AMBIGUOUS: "AMBIGUOUS (SL and TP both inside one bar)",
    Outcome.FORCE_CLOSED: "OPEN AT FORCE-CLOSE (09:00 next day, no SL/TP hit)",
}


def outcome_text(outcome: Outcome) -> str:
    return _OUTCOME_TEXT[outcome]


def _range_pips(session: BarBlock) -> float:
    return to_pips(session.range)


def _cancelled(session: BarBlock) -> bool:
    return _range_pips(session) > MAX_RANGE_PIPS


@dataclass
class DayResult:
    reference_session: BarBlock
    pending_long: PendingPosition = field(init=False)
    pending_short: PendingPosition = field(init=False)
    long: Position | None = None
    short: Position | None = None

    def __post_init__(self) -> None:
        mid = self.reference_session.mid
        self.pending_long = PendingPosition.for_level(self.reference_session.high_value, mid, RISK_REWARD)
        self.pending_short = PendingPosition.for_level(self.reference_session.low_value, mid, RISK_REWARD)

    @property
    def window_start(self) -> datetime:
        return datetime.combine(self.reference_session.day, TOKYO_END)

    @property
    def breakout_cutoff(self) -> datetime:
        return datetime.combine(self.reference_session.day + timedelta(days=1), _time(0, 0))

    @property
    def window_end(self) -> datetime:
        return datetime.combine(self.reference_session.day + timedelta(days=1), TOKYO_END)


class TokyoBreakoutStrategy:
    """Encapsulates the Tokyo Session Breakout rules (see
    tokyo-session-breakout.md): given one chronological stream of Bars,
    decides each day's Tokyo range, whether it's tradeable, and simulates
    the breakout/SL/TP/force-close outcome for both sides.

    `calculate()` consumes its `bars` argument exactly once."""

    def calculate(self, bars: Iterable[Bar]) -> list[DayResult]:
        """One pass over `bars` (must be chronological). Folds Tokyo-session
        bars into each day's BarBlock; as soon as a day's Tokyo session
        closes (09:00), decides whether it trades and, if so, opens it as
        the active trade window -- which runs until the next day's Tokyo
        session closes, so the two are contiguous and one pass covers both."""
        sessions: dict[_date, BarBlock] = {}
        results: list[DayResult] = []
        current: DayResult | None = None
        next_day_to_resolve: _date | None = None

        def resolve_up_to(dt: datetime) -> None:
            nonlocal current, next_day_to_resolve
            while next_day_to_resolve is not None and dt >= datetime.combine(next_day_to_resolve, TOKYO_END):
                boundary = datetime.combine(next_day_to_resolve, TOKYO_END)
                if current is not None and boundary >= current.window_end:
                    self._force_close(current)
                    results.append(current)
                    current = None
                session = sessions.get(next_day_to_resolve)
                if session is not None:
                    if _cancelled(session):
                        results.append(DayResult(session))
                    elif current is None:
                        current = DayResult(session)
                next_day_to_resolve += timedelta(days=1)

        for bar in bars:
            if next_day_to_resolve is None:
                next_day_to_resolve = bar.dt.date()

            t = bar.dt.time()
            if TOKYO_START <= t < TOKYO_END:
                sessions.setdefault(bar.dt.date(), BarBlock()).add(bar)

            resolve_up_to(bar.dt)

            if current is not None and bar.dt >= current.window_start:
                self._process_bar(current, bar)

        if current is not None:
            self._force_close(current)
            results.append(current)

        return self._all_results(sessions, results)

    def _all_results(self, sessions: dict[_date, BarBlock], results: list[DayResult]) -> list[DayResult]:
        by_day = {r.reference_session.day: r for r in results}
        for day, session in sessions.items():
            if day not in by_day:
                by_day[day] = DayResult(session)
        return [by_day[d] for d in sorted(by_day)]

    def _process_bar(self, result: DayResult, bar: Bar) -> None:
        session = result.reference_session
        result.long = self._process_side(
            result, bar, result.long, result.pending_long, True, bar.high > session.high_value
        )
        result.short = self._process_side(
            result, bar, result.short, result.pending_short, False, bar.low < session.low_value
        )

    def _process_side(
        self, result: DayResult, bar: Bar, position: Position | None, pending: PendingPosition, is_long: bool, breaks_level: bool
    ) -> Position | None:
        if position is None:
            if bar.dt < result.breakout_cutoff and breaks_level:
                position = pending.open_position(bar.dt)
                self._check_resolution(position, bar, is_long)
            return position
        if position.resolved_dt is None:
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
            position.resolved_dt = bar.dt
        elif hit_tp:
            position.outcome = Outcome.TP_HIT
            position.resolved_dt = bar.dt
            position.resolved_price = position.tp
        elif hit_sl:
            position.outcome = Outcome.SL_HIT
            position.resolved_dt = bar.dt
            position.resolved_price = position.sl

    def _force_close(self, result: DayResult) -> None:
        for position in (result.long, result.short):
            if position is not None and position.is_resolved is False:
                position.outcome = Outcome.FORCE_CLOSED
                position.resolved_dt = result.window_end


def _fmt_price(value: float) -> str:
    return f"{value:.{PRICE_DECIMALS}f}"


def _fmt_pips(value: float) -> str:
    return f"{value:.1f}p"


def _fmt_position(label: str, position: Position | None) -> str:
    if position is None:
        return f"  {label}: {outcome_text(Outcome.NONE)}"

    header = (
        f"  {label}: triggered {position.entry_dt:%Y-%m-%d %H:%M} @ "
        f"{_fmt_price(position.entry_price)}  "
        f"(SL {_fmt_pips(to_pips(position.risk_value))} @ {_fmt_price(position.sl)}, "
        f"TP {_fmt_pips(to_pips(position.reward_value))} @ {_fmt_price(position.tp)})"
    )
    if not position.is_resolved:
        detail = "    -> still open (not yet resolved)"
    elif position.outcome == Outcome.FORCE_CLOSED:
        detail = f"    -> {outcome_text(Outcome.FORCE_CLOSED)} at {position.resolved_dt:%Y-%m-%d %H:%M}"
    elif position.outcome == Outcome.AMBIGUOUS:
        detail = f"    -> {outcome_text(Outcome.AMBIGUOUS)} at {position.resolved_dt:%Y-%m-%d %H:%M}"
    else:
        detail = (
            f"    -> {outcome_text(position.outcome)} at {position.resolved_dt:%Y-%m-%d %H:%M} "
            f"@ {_fmt_price(position.resolved_price)}"
        )
    return header + "\n" + detail


def print_bar_block(bar_block: BarBlock, indent: str) -> None:
    print(f"{indent}Open: {_fmt_price(bar_block.open_value)} ({bar_block.open_dt})")
    print(f"{indent}High: {_fmt_price(bar_block.high_value)} ({bar_block.high_dt})")
    print(f"{indent}Low: {_fmt_price(bar_block.low_value)} ({bar_block.low_dt})")
    print(f"{indent}Close: {_fmt_price(bar_block.close_value)} ({bar_block.close_dt})")
    print(f"{indent}Range: {_fmt_pips(_range_pips(bar_block))}")


def print_report(results: list[DayResult]) -> None:
    counts = {"cancelled": 0, "no_session": 0, "days": 0}
    outcome_counts: dict[Outcome, int] = {o: 0 for o in Outcome}
    triggered_sides = 0

    for result in results:
        session = result.reference_session
        counts["days"] += 1
        print(f"=== {session.day.isoformat()} (Tokyo 00:00-09:00) ===")
        print_bar_block(session, "  ")

        if _cancelled(session):
            counts["cancelled"] += 1
            print(f"  CANCELLED (> {MAX_RANGE_PIPS:.0f}p threshold)\n")
            continue

        risk_pips = _range_pips(session) / 2
        print(f"  SL: {_fmt_pips(risk_pips)}   TP: {_fmt_pips(risk_pips * RISK_REWARD)}")
        print(_fmt_position("LONG ", result.long))
        print(_fmt_position("SHORT", result.short))
        print()

        for position in (result.long, result.short):
            if position is not None:
                triggered_sides += 1
                outcome_counts[position.outcome] += 1

    total = counts["days"]
    traded_days = total - counts["cancelled"]
    print("=== summary ===")
    print(f"  Tokyo sessions: {total}   cancelled (range > {MAX_RANGE_PIPS:.0f}p): {counts['cancelled']}")
    print(f"  Eligible days: {traded_days}   sides triggered: {triggered_sides}")
    for outcome in (Outcome.TP_HIT, Outcome.SL_HIT, Outcome.AMBIGUOUS, Outcome.FORCE_CLOSED):
        print(f"    {outcome.name}: {outcome_counts[outcome]}")
    PL = outcome_counts[Outcome.TP_HIT] * RISK_REWARD - outcome_counts[Outcome.SL_HIT]
    print(f"  P/L: {PL} %")


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
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    source_path = args.source
    bars = retrieve_bars(source_path)

    strategy = TokyoBreakoutStrategy()
    results = strategy.calculate(bars)

    if not results:
        raise SystemExit("error: no Tokyo-session bars found in source")

    print_report(results)


if __name__ == "__main__":
    main()
