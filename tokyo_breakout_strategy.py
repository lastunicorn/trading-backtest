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
from enum import Enum
from pathlib import Path

from domain.bar_block import BarBlock
from domain.shift_bars import shift_bars
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import Bar, iterate_bars

PIP = 0.0001
PRICE_DECIMALS = 5

TOKYO_START = _time(0, 0)
TOKYO_END = _time(9, 0)  # exclusive
MAX_RANGE_PIPS = 30.0
RISK_REWARD = 2.0


def to_pips(price_diff: float) -> float:
    return price_diff / PIP


class Outcome(Enum):
    NOT_TRIGGERED = "not triggered (H/L not broken by 00:00 next day)"
    TP_HIT = "TP HIT"
    SL_HIT = "SL HIT"
    AMBIGUOUS = "AMBIGUOUS (SL and TP both inside one bar)"
    FORCE_CLOSED = "OPEN AT FORCE-CLOSE (09:00 next day, no SL/TP hit)"


def _range_pips(session: BarBlock) -> float:
    return to_pips(session.range)


def _cancelled(session: BarBlock) -> bool:
    return _range_pips(session) > MAX_RANGE_PIPS


@dataclass
class Position:
    """One side (long or short) of a day's trade, if it ever triggers."""

    entry_dt: datetime | None = None
    entry_price: float | None = None
    sl: float | None = None
    tp: float | None = None
    outcome: Outcome = Outcome.NOT_TRIGGERED
    resolved_dt: datetime | None = None
    resolved_price: float | None = None

    @property
    def triggered(self) -> bool:
        return self.entry_dt is not None

    @property
    def risk_pips(self) -> float | None:
        if self.entry_price is None or self.sl is None:
            return None
        return to_pips(abs(self.entry_price - self.sl))

    @property
    def reward_pips(self) -> float | None:
        if self.entry_price is None or self.tp is None:
            return None
        return to_pips(abs(self.tp - self.entry_price))


@dataclass
class DayResult:
    session: BarBlock
    long: Position = field(default_factory=Position)
    short: Position = field(default_factory=Position)

    @property
    def window_start(self) -> datetime:
        return datetime.combine(self.session.day, TOKYO_END)

    @property
    def breakout_cutoff(self) -> datetime:
        return datetime.combine(self.session.day + timedelta(days=1), _time(0, 0))

    @property
    def window_end(self) -> datetime:
        return datetime.combine(self.session.day + timedelta(days=1), TOKYO_END)


def _stream_bars(paths: Iterable[Path]) -> Iterator[Bar]:
    def _raw() -> Iterator[Bar]:
        for path in paths:
            yield from iterate_bars(str(path), strict=False)

    return shift_bars(_raw(), timedelta(hours=5))


def compute_tokyo_sessions(paths: list[Path]) -> dict[_date, BarBlock]:
    """One pass: every day's Tokyo (00:00-09:00) high/low/open/close."""
    sessionsByDate: dict[_date, BarBlock] = {}

    for bar in _stream_bars(paths):
        t = bar.dt.time()
        if not (TOKYO_START <= t < TOKYO_END):
            continue
        date = bar.dt.date()
        block = sessionsByDate.get(date)
        if block is None:
            block = BarBlock()
            sessionsByDate[date] = block
        block.add(bar)

    return sessionsByDate


def _open_position(position: Position, entry_dt: datetime, entry_price: float, mid: float) -> None:
    risk = abs(entry_price - mid)
    position.entry_dt = entry_dt
    position.entry_price = entry_price
    position.sl = mid
    position.tp = entry_price + RISK_REWARD * risk * (1 if entry_price > mid else -1)


def _check_resolution(position: Position, bar: Bar, is_long: bool) -> None:
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


def _process_bar(result: DayResult, bar: Bar) -> None:
    session = result.session
    mid = session.mid

    for position, is_long, breaks_level in (
        (result.long, True, bar.high > session.high_value),
        (result.short, False, bar.low < session.low_value),
    ):
        if not position.triggered:
            if bar.dt < result.breakout_cutoff and breaks_level:
                entry_price = session.high_value if is_long else session.low_value
                _open_position(position, bar.dt, entry_price, mid)
                _check_resolution(position, bar, is_long)
        elif position.resolved_dt is None:
            _check_resolution(position, bar, is_long)


def _force_close(result: DayResult) -> None:
    for position in (result.long, result.short):
        if position.triggered and position.resolved_dt is None:
            position.outcome = Outcome.FORCE_CLOSED
            position.resolved_dt = result.window_end


def simulate_trades(paths: list[Path], sessions: dict[_date, BarBlock]) -> list[DayResult]:
    """Second pass: walk the bars again, this time simulating each day's trade
    window [09:00, 09:00 next day) in order, using the H/L already known from
    the first pass."""
    trade_days = sorted(d for d, s in sessions.items() if not _cancelled(s))
    results: list[DayResult] = []

    idx = 0
    current: DayResult | None = None
    if trade_days:
        current = DayResult(sessions[trade_days[0]])

    def advance_past(dt: datetime) -> None:
        nonlocal idx, current
        while current is not None and dt >= current.window_end:
            _force_close(current)
            results.append(current)
            idx += 1
            current = DayResult(sessions[trade_days[idx]]) if idx < len(trade_days) else None

    for bar in _stream_bars(paths):
        advance_past(bar.dt)
        if current is not None and bar.dt >= current.window_start:
            _process_bar(current, bar)

    if current is not None:
        _force_close(current)
        results.append(current)
        idx += 1

    # Trade days for which no bar at or after window_start ever arrived
    # (dataset ends right at/after the Tokyo session, before any afternoon
    # bar) -- record them untriggered rather than dropping them silently.
    for d in trade_days[idx:]:
        results.append(DayResult(sessions[d]))

    return results


def _all_results(sessions: dict[_date, BarBlock], traded: list[DayResult]) -> list[DayResult]:
    by_day = {r.session.day: r for r in traded}
    for day, session in sessions.items():
        if _cancelled(session) and day not in by_day:
            by_day[day] = DayResult(session)
    return [by_day[d] for d in sorted(by_day)]


def _fmt_price(value: float) -> str:
    return f"{value:.{PRICE_DECIMALS}f}"


def _fmt_pips(value: float) -> str:
    return f"{value:.1f}p"


def _fmt_position(label: str, position: Position) -> str:
    if not position.triggered:
        return f"  {label}: {Outcome.NOT_TRIGGERED.value}"

    header = (
        f"  {label}: triggered {position.entry_dt:%Y-%m-%d %H:%M} @ "
        f"{_fmt_price(position.entry_price)}  "
        f"(SL {_fmt_pips(position.risk_pips)} @ {_fmt_price(position.sl)}, "
        f"TP {_fmt_pips(position.reward_pips)} @ {_fmt_price(position.tp)})"
    )
    if position.outcome == Outcome.FORCE_CLOSED:
        detail = f"    -> {Outcome.FORCE_CLOSED.value} at {position.resolved_dt:%Y-%m-%d %H:%M}"
    elif position.outcome == Outcome.AMBIGUOUS:
        detail = f"    -> {Outcome.AMBIGUOUS.value} at {position.resolved_dt:%Y-%m-%d %H:%M}"
    else:
        detail = (
            f"    -> {position.outcome.value} at {position.resolved_dt:%Y-%m-%d %H:%M} "
            f"@ {_fmt_price(position.resolved_price)}"
        )
    return header + "\n" + detail


def print_report(results: list[DayResult]) -> None:
    counts = {"cancelled": 0, "no_session": 0, "days": 0}
    outcome_counts: dict[Outcome, int] = {o: 0 for o in Outcome}
    triggered_sides = 0

    for result in results:
        session = result.session
        counts["days"] += 1
        print(f"=== {session.day.isoformat()} (Tokyo 00:00-09:00) ===")
        
        print(f"  Open: {_fmt_price(session.open_value)} ({session.open_dt})")
        print(f"  High: {_fmt_price(session.high_value)} ({session.high_dt})")
        print(f"  Low: {_fmt_price(session.low_value)} ({session.low_dt})")
        print(f"  Close: {_fmt_price(session.close_value)} ({session.close_dt})")

        print(f"  Range: {_fmt_pips(_range_pips(session))}", end="")

        if _cancelled(session):
            counts["cancelled"] += 1
            print(f"  -> CANCELLED (> {MAX_RANGE_PIPS:.0f}p threshold)\n")
            continue

        risk_pips = _range_pips(session) / 2
        print(f"   SL: {_fmt_pips(risk_pips)}   TP: {_fmt_pips(risk_pips * RISK_REWARD)}")
        print(_fmt_position("LONG ", result.long))
        print(_fmt_position("SHORT", result.short))
        print()

        for position in (result.long, result.short):
            if position.triggered:
                triggered_sides += 1
                outcome_counts[position.outcome] += 1

    total = counts["days"]
    traded_days = total - counts["cancelled"]
    print("=== summary ===")
    print(f"  Tokyo sessions: {total}   cancelled (range > {MAX_RANGE_PIPS:.0f}p): {counts['cancelled']}")
    print(f"  Eligible days: {traded_days}   sides triggered: {triggered_sides}")
    for outcome in (Outcome.TP_HIT, Outcome.SL_HIT, Outcome.AMBIGUOUS, Outcome.FORCE_CLOSED):
        print(f"    {outcome.name}: {outcome_counts[outcome]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("source", help="a single M1 csv export, or a folder of them")
    args = parser.parse_args()

    paths = find_files(args.source)
    if not paths:
        parser.error(f"no csv files found at {args.source!r}")

    print(f"Reading {len(paths)} file(s) from {args.source}\n")

    sessions = compute_tokyo_sessions(paths)
    if not sessions:
        parser.error("no Tokyo-session bars found in source")

    traded = simulate_trades(paths, sessions)
    results = _all_results(sessions, traded)
    print_report(results)


if __name__ == "__main__":
    main()
