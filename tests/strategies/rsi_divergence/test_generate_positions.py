"""Tests for `strategies.rsi_divergence.RsiDivergence.generate_positions`."""

import pytest

from domain.pandas_approach.divergence import Category, Direction
from domain.pandas_approach.position import Side
from strategies.rsi_divergence import RsiDivergence

from ._fakes import ENTRY, PIVOT, at, data, divergence, script


def test_bullish_divergence_is_a_long_with_stop_below_the_pivot_low(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    [position] = RsiDivergence(risk_reward=2.0, stop_buffer_pips=1.0).generate_positions(data(pivot_low=1.0980))

    assert position.side == Side.LONG
    assert position.open_dt == at(ENTRY)
    assert position.open_price == 1.1000
    assert position.sl == pytest.approx(1.0979)            # pivot low - 1 pip
    assert position.tp == pytest.approx(1.1042)            # 2 x the 21-pip risk
    assert position.exit_dt is None
    assert position.tag == f"bullish divergence, pivot {at(PIVOT):%Y-%m-%d %H:%M}"


def test_bearish_divergence_is_a_short_with_stop_above_the_pivot_high(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BEARISH, 75, 65))

    [position] = RsiDivergence(risk_reward=1.5, stop_buffer_pips=0).generate_positions(data(pivot_high=1.1020))

    assert position.side == Side.SHORT
    assert position.sl == pytest.approx(1.1020)
    assert position.tp == pytest.approx(1.0970)            # 1.5 x the 20-pip risk


def test_entry_is_the_open_after_pivot_confirmation(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    [position] = RsiDivergence(pivot_right=3).generate_positions(data())

    assert position.open_dt == at(PIVOT + 3 + 1)


def test_divergences_failing_the_band_filter_are_skipped(monkeypatch) -> None:
    script(
        monkeypatch,
        divergence(Direction.BULLISH, 40, 45),     # starts inside the band
        divergence(Direction.BULLISH, 20, 25),     # never re-enters it
    )

    assert RsiDivergence().generate_positions(data()) == []


def test_hidden_divergences_are_never_traded(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35, category=Category.HIDDEN))

    assert RsiDivergence().generate_positions(data()) == []


def test_long_whose_entry_is_already_below_the_pivot_low_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35))

    assert RsiDivergence().generate_positions(data(pivot_low=1.0980, entry_open=1.0975)) == []


def test_short_whose_entry_is_already_above_the_pivot_high_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BEARISH, 75, 65))

    assert RsiDivergence().generate_positions(data(pivot_high=1.1020, entry_open=1.1025)) == []


def test_divergence_too_close_to_the_end_to_confirm_is_skipped(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35, end_bar=57))    # 57 + 6 is past bar 59

    assert RsiDivergence().generate_positions(data(n=60)) == []


def test_one_position_per_signal(monkeypatch) -> None:
    script(monkeypatch, divergence(Direction.BULLISH, 25, 35), divergence(Direction.BEARISH, 75, 65, end_bar=40))

    positions = RsiDivergence().generate_positions(data())

    assert [p.side for p in positions] == [Side.LONG, Side.SHORT]


def test_runs_on_real_divergence_detection() -> None:
    # No scripting: the flat fixture has no RSI pivots, so no trades -- and no crash.
    assert RsiDivergence().generate_positions(data()) == []
