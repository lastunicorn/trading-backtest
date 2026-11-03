"""Tests for `USDJPY`'s frozen specification.

Unlike the other majors, JPY pairs are quoted two decimals shorter: a pip is
the 2nd decimal (0.01) rather than the 4th, and the tradeable tick is the 3rd
(0.001) rather than the 5th.
"""

import pytest

from domain.symbol import SymbolCategory, USDJPY


def test_specification() -> None:
    assert USDJPY.name == "U.S. Dollar / Japanese Yen"
    assert USDJPY.ticker == "USDJPY"
    assert USDJPY.pip_size == 0.01
    assert USDJPY.tick_size == 0.001
    assert USDJPY.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert USDJPY.price_decimals == 3


def test_to_pips_uses_the_jpy_pip_size() -> None:
    assert USDJPY.to_pips(0.15) == pytest.approx(15.0)
