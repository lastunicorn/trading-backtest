"""`DailyStrategyBase` cannot be instantiated directly -- `_create_session`
is abstract, so only a concrete subclass (see `FakeDailyStrategy` in
`_fakes.py`, or a real one like `session_breakout_strategy.SessionBreakoutStrategy`)
can be constructed."""

import pytest

from domain.daily_strategy_base import DailyStrategyBase


def test_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        DailyStrategyBase()
