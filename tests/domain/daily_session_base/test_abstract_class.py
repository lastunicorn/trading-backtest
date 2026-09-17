"""`DailySessionBase` cannot be instantiated directly -- `_process_bar` and
`_close_all_positions` are abstract, so only a concrete subclass (see
`FakeDailySession` in `_fakes.py`, or a real one like
`session_breakout_strategy.DailySession`) can be constructed."""

from datetime import date

import pytest

from domain.bar_approach.daily_session_base import DailySessionBase


def test_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        DailySessionBase(date(2026, 1, 15))
