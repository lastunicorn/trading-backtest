"""Tests for `USDCAD`'s frozen specification."""

from domain.symbol import SymbolCategory, USDCAD


def test_specification() -> None:
    assert USDCAD.name == "U.S. Dollar / Canadian Dollar"
    assert USDCAD.ticker == "USDCAD"
    assert USDCAD.pip_size == 0.0001
    assert USDCAD.tick_size == 0.00001
    assert USDCAD.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert USDCAD.price_decimals == 5
