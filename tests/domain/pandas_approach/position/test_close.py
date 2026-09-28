"""Tests for `domain.pandas_approach.position.Position.close`."""

import pandas as pd
import pytest

from domain.pandas_approach.position import PositionOutcome

from ._fakes import T0, long_position

LATER = T0 + pd.Timedelta("15min")


@pytest.mark.parametrize(
    ("outcome", "price"),
    [
        (PositionOutcome.TAKE_PROFIT_HIT, 1.1040),
        (PositionOutcome.STOP_LOSS_HIT, 1.0980),
        (PositionOutcome.MANUAL_CLOSE, 1.1012),
        (PositionOutcome.END_OF_DATA, 1.1007),
    ],
)
def test_records_time_price_and_outcome(outcome: PositionOutcome, price: float) -> None:
    position = long_position()

    position.close(LATER, price, outcome)

    assert position.close_dt == LATER
    assert position.close_price == price
    assert position.outcome == outcome


def test_ambiguous_outcome_closes_without_a_price() -> None:
    position = long_position()

    position.close(LATER, None, PositionOutcome.AMBIGUOUS)

    assert position.outcome == PositionOutcome.AMBIGUOUS
    assert position.close_price is None


def test_ambiguous_outcome_with_a_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        long_position().close(LATER, 1.1040, PositionOutcome.AMBIGUOUS)


def test_non_ambiguous_outcome_without_a_price_is_rejected() -> None:
    with pytest.raises(ValueError, match="AMBIGUOUS"):
        long_position().close(LATER, None, PositionOutcome.STOP_LOSS_HIT)


def test_closing_with_outcome_open_is_rejected() -> None:
    with pytest.raises(ValueError, match="OPEN"):
        long_position().close(LATER, 1.1040, PositionOutcome.OPEN)


def test_closing_before_open_is_rejected() -> None:
    with pytest.raises(ValueError, match="before open_dt"):
        long_position().close(T0 - pd.Timedelta("5min"), 1.1040, PositionOutcome.TAKE_PROFIT_HIT)


def test_closing_on_the_entry_bar_is_allowed() -> None:
    position = long_position()

    position.close(T0, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    assert position.close_dt == T0


def test_closing_twice_is_rejected_and_keeps_the_first_close() -> None:
    position = long_position()
    position.close(LATER, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)

    with pytest.raises(ValueError, match="already closed"):
        position.close(LATER + pd.Timedelta("5min"), 1.0980, PositionOutcome.STOP_LOSS_HIT)

    assert position.outcome == PositionOutcome.TAKE_PROFIT_HIT
    assert position.close_dt == LATER
