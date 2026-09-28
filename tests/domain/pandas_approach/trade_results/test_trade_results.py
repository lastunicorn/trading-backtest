"""Tests for `domain.pandas_approach.trade_results.trade_results`."""

import math

import pandas as pd
import pytest

from domain.pandas_approach.position import FRAME_COLUMNS, Position, PositionOutcome, Side, positions_to_frame
from domain.pandas_approach.trade_results import RESULT_COLUMNS, trade_results
from domain.symbol import EurUsd, UsdJpy

T0 = pd.Timestamp("2026-01-05 10:00")


def _closed(side: Side, close_price: float | None, outcome: PositionOutcome, minutes: int = 30, **levels) -> Position:
    defaults = dict(sl=1.0980, tp=1.1040) if side == Side.LONG else dict(sl=1.1020, tp=1.0960)
    defaults.update(levels)
    position = Position(T0, 1.1000, side, **defaults)
    position.close(T0 + pd.Timedelta(minutes=minutes), close_price, outcome)
    return position


def _results(positions, cost=1.7, symbol=EurUsd()):
    frame = positions_to_frame(positions)
    return trade_results(frame, symbol, pd.Series(cost, index=frame.index, dtype="float64"))


def test_appends_result_columns_after_the_position_columns() -> None:
    result = _results([_closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)])

    assert list(result.columns) == [*FRAME_COLUMNS, *RESULT_COLUMNS]


def test_long_winner() -> None:
    row = _results([_closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)]).iloc[0]

    assert row["gross_pips"] == pytest.approx(40)
    assert row["cost_pips"] == 1.7
    assert row["net_pips"] == pytest.approx(38.3)
    assert row["risk_pips"] == pytest.approx(20)
    assert row["net_r"] == pytest.approx(38.3 / 20)
    assert row["duration_min"] == 30


def test_short_winner_is_positive_when_price_falls() -> None:
    row = _results([_closed(Side.SHORT, 1.0960, PositionOutcome.TAKE_PROFIT_HIT)]).iloc[0]

    assert row["gross_pips"] == pytest.approx(40)
    assert row["risk_pips"] == pytest.approx(20)


def test_short_loser_is_negative_when_price_rises() -> None:
    row = _results([_closed(Side.SHORT, 1.1020, PositionOutcome.STOP_LOSS_HIT)]).iloc[0]

    assert row["gross_pips"] == pytest.approx(-20)
    assert row["net_pips"] == pytest.approx(-21.7)
    assert row["net_r"] == pytest.approx(-21.7 / 20)


def test_ambiguous_trade_has_no_pnl_but_keeps_risk_and_duration() -> None:
    row = _results([_closed(Side.LONG, None, PositionOutcome.AMBIGUOUS)]).iloc[0]

    assert math.isnan(row["gross_pips"])
    assert math.isnan(row["net_pips"])
    assert math.isnan(row["net_r"])
    assert row["risk_pips"] == pytest.approx(20)
    assert row["duration_min"] == 30


def test_pips_use_the_symbol_pip_size() -> None:
    position = Position(T0, 150.00, Side.LONG, sl=149.80, tp=150.40)
    position.close(T0 + pd.Timedelta("5min"), 150.40, PositionOutcome.TAKE_PROFIT_HIT)

    row = _results([position], cost=0.0, symbol=UsdJpy()).iloc[0]

    assert row["gross_pips"] == pytest.approx(40)
    assert row["risk_pips"] == pytest.approx(20)


def test_per_trade_costs_are_applied_row_by_row() -> None:
    frame = positions_to_frame([
        _closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT),
        _closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT),
    ])

    result = trade_results(frame, EurUsd(), pd.Series([0.5, 2.0], index=frame.index))

    assert result["net_pips"].tolist() == pytest.approx([39.5, 38.0])


def test_misaligned_costs_are_rejected() -> None:
    frame = positions_to_frame([_closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)])

    with pytest.raises(ValueError, match="aligned"):
        trade_results(frame, EurUsd(), pd.Series([1.7], index=[5]))


def test_input_frame_is_left_untouched() -> None:
    frame = positions_to_frame([_closed(Side.LONG, 1.1040, PositionOutcome.TAKE_PROFIT_HIT)])
    before = frame.copy()

    trade_results(frame, EurUsd(), pd.Series(1.7, index=frame.index))

    pd.testing.assert_frame_equal(frame, before)


def test_no_trades_gives_an_empty_frame_with_every_column() -> None:
    result = _results([])

    assert result.empty
    assert list(result.columns) == [*FRAME_COLUMNS, *RESULT_COLUMNS]
