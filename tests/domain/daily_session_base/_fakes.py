"""Shared test doubles for `DailySessionBase` tests -- not a test module
itself (no `test_` prefix), so pytest never collects it.

`FakeDailySession` is the minimal concrete subclass the tests need: it spans
`span_days` calendar days from `day` (matching the base class's requirement
that a subclass's `__post_init__` set `start_dt`/`end_dt`), records every bar
handed to `_process_bar` before delegating to the base's default body, and
closes out open positions on `_close_all_positions` the same way
`session_breakout_strategy.DailySession` does. A test that needs a narrower
or differently-placed window overrides `start_dt`/`end_dt` directly on the
instance after construction -- they're plain attributes, not derived.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time as _time, timedelta

from domain.bar_approach.bar import Bar
from domain.bar_approach.daily_session_base import DailySessionBase


@dataclass
class FakeDailySession(DailySessionBase):
    span_days: int = 1

    processed_bars: list[Bar] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self.start_dt = datetime.combine(self.day, _time.min)
        self.end_dt = self.start_dt + timedelta(days=self.span_days)

    def _process_bar(self, bar: Bar) -> None:
        self.processed_bars.append(bar)
        super()._process_bar(bar)

    def _close_all_positions(self, at: datetime) -> None:
        for position in self._positions:
            if not position.is_closed:
                position.close(at)


def make_bar(
    dt: datetime,
    *,
    open: float = 1.1000,
    high: float = 1.1010,
    low: float = 1.0990,
    close: float = 1.1005,
) -> Bar:
    return Bar(dt=dt, open=open, high=high, low=low, close=close)
