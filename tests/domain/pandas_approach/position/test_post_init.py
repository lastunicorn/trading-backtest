"""Tests for `domain.pandas_approach.position.Position.__post_init__`."""

import pandas as pd
import pytest

from domain.pandas_approach.position import PositionOutcome

from ._fakes import T0, long_position, short_position


def test_valid_long_position_starts_open_with_no_close_fields() -> None:
    position = long_position()

    assert position.outcome == PositionOutcome.OPEN
    assert position.close_dt is None
    assert position.close_price is None
    assert position.exit_dt is None
    assert position.tag == ""


def test_valid_short_position_is_accepted() -> None:
    assert short_position().outcome == PositionOutcome.OPEN


@pytest.mark.parametrize(
    "overrides",
    [
        dict(sl=1.1010),              # SL above entry
        dict(tp=1.0990),              # TP below entry
        dict(sl=1.1000),              # SL on entry
        dict(tp=1.1000),              # TP on entry
    ],
)
def test_long_with_misplaced_levels_is_rejected(overrides: dict) -> None:
    with pytest.raises(ValueError, match="long position"):
        long_position(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        dict(sl=1.0990),              # SL below entry
        dict(tp=1.1010),              # TP above entry
    ],
)
def test_short_with_misplaced_levels_is_rejected(overrides: dict) -> None:
    with pytest.raises(ValueError, match="short position"):
        short_position(**overrides)


def test_exit_dt_after_open_is_accepted() -> None:
    position = long_position(exit_dt=T0 + pd.Timedelta("4h"))

    assert position.exit_dt == T0 + pd.Timedelta("4h")


@pytest.mark.parametrize("offset", ["0min", "-5min"])
def test_exit_dt_not_after_open_is_rejected(offset: str) -> None:
    with pytest.raises(ValueError, match="exit_dt"):
        long_position(exit_dt=T0 + pd.Timedelta(offset))
