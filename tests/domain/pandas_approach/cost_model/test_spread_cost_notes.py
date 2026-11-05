"""Tests for `domain.pandas_approach.cost_model.SpreadCost.notes`."""

import pytest

from domain.pandas_approach.cost_model import SpreadCost
from domain.pandas_approach.side import Side

from ._fakes import data, trades

NAN = float("nan")


def test_no_note_when_every_trade_has_a_spread() -> None:
    assert SpreadCost().notes(trades((Side.LONG, 0, 3)), data([0.1, NAN, 0.3, 0.4])) == []


def test_trades_without_spread_are_counted_and_listed() -> None:
    frame = trades((Side.LONG, 1, 3), (Side.SHORT, 0, 1), (Side.LONG, 0, 1))

    [note] = SpreadCost().notes(frame, data([0.1, NAN, 0.3, 0.4]))

    # The long opening on bar 1 and the short closing on it; the long opening on bar 0 paid 0.1.
    assert note.startswith("2 trade(s) charged 0 spread")
    assert "Opened 2026-01-05 10:00, 2026-01-05 10:05." in note


def test_a_long_list_is_cut_short() -> None:
    frame = trades(*[(Side.LONG, 1, 2)] * 12)

    [note] = SpreadCost().notes(frame, data([0.1, NAN, 0.3, 0.4]))

    assert note.startswith("12 trade(s)")
    assert note.endswith("and 2 more.")


def test_no_trades_no_note() -> None:
    assert SpreadCost().notes(trades(), data([NAN] * 4)) == []


def test_missing_spread_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="FixedCost"):
        SpreadCost().notes(trades((Side.LONG, 0, 1)), data(spreads=None))
