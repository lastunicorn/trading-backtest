"""Tests for `UsdJpy`'s frozen specification.

Unlike the other majors, JPY pairs are quoted two decimals shorter: a pip is
the 2nd decimal (0.01) rather than the 4th, and the tradeable tick is the 3rd
(0.001) rather than the 5th.
"""

import pytest

from domain.symbol import Symbol, SymbolCategory, UsdJpy


def test_is_a_symbol() -> None:
    assert isinstance(UsdJpy(), Symbol)


def test_specification() -> None:
    usd_jpy = UsdJpy()
    assert usd_jpy.name == "U.S. Dollar / Japanese Yen"
    assert usd_jpy.ticker == "USDJPY"
    assert usd_jpy.pip_size == 0.01
    assert usd_jpy.tick_size == 0.001
    assert usd_jpy.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert UsdJpy().price_decimals == 3


def test_to_pips_uses_the_jpy_pip_size() -> None:
    assert UsdJpy().to_pips(0.15) == pytest.approx(15.0)
