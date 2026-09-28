"""Tests for `domain.pandas_approach.position.Position.is_closed`."""

import pandas as pd

from domain.pandas_approach.position import PositionOutcome

from ._fakes import T0, long_position


def test_new_position_is_not_closed() -> None:
    assert not long_position().is_closed


def test_position_is_closed_after_close() -> None:
    position = long_position()

    position.close(T0 + pd.Timedelta("5min"), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    assert position.is_closed
