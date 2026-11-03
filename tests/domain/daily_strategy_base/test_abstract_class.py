"""`DailyStrategyBase` cannot be instantiated directly -- `_create_session`
is abstract, so only a concrete subclass (see `FakeDailyStrategy` in
`_fakes.py`; the only real one was the removed
`session_breakout_strategy.SessionBreakoutStrategy`) can be constructed."""

import pytest

from domain.bar_approach.daily_strategy_base import DailyStrategyBase


def test_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        DailyStrategyBase()
