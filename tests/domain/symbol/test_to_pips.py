"""Tests for `Symbol.to_pips`."""

import pytest

from domain.symbol import EurUsd, Symbol


def _symbol(pip_size: float) -> Symbol:
    return Symbol(name="Test", ticker="TST", pip_size=pip_size, tick_size=pip_size)


def test_converts_a_price_difference_to_pips() -> None:
    symbol = _symbol(pip_size=0.0001)
    assert symbol.to_pips(0.0025) == pytest.approx(25.0)


def test_scales_with_pip_size() -> None:
    price_diff = 0.02
    assert _symbol(pip_size=0.0001).to_pips(price_diff) == pytest.approx(200.0)
    assert _symbol(pip_size=0.01).to_pips(price_diff) == pytest.approx(2.0)


def test_zero_difference_is_zero_pips() -> None:
    assert EurUsd().to_pips(0.0) == 0.0


def test_negative_difference_stays_negative() -> None:
    assert EurUsd().to_pips(-0.0010) == pytest.approx(-10.0)
