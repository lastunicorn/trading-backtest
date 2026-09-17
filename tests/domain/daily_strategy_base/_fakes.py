"""Shared test doubles for `DailyStrategyBase` tests -- not a test module
itself (no `test_` prefix), so pytest never collects it.

Reuses `FakeDailySession` from the sibling `daily_session_base` test package
rather than redefining it: `DailyStrategyBase` only needs *some* concrete
`DailySessionBase`, and `FakeDailySession`'s `span_days` already lets a test
build one that stays live across more than one calendar day, which is what
exercising "a still-resolving earlier day's session" (see
`DailyStrategyBase.add_bar`'s docstring) requires.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date

from domain.daily_session_base import DailySessionBase
from domain.daily_strategy_base import DailyStrategyBase
from tests.domain.daily_session_base._fakes import FakeDailySession, make_bar

__all__ = ["FakeDailyStrategy", "make_bar"]


@dataclass
class FakeDailyStrategy(DailyStrategyBase):
    span_days: int = 1

    def _create_session(self, day: _date) -> DailySessionBase:
        return FakeDailySession(day, span_days=self.span_days)
