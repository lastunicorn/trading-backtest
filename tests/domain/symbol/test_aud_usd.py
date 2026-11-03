"""Tests for `AUDUSD`'s frozen specification."""

from domain.symbol import AUDUSD, SymbolCategory


def test_specification() -> None:
    assert AUDUSD.name == "Australian Dollar / U.S. Dollar"
    assert AUDUSD.ticker == "AUDUSD"
    assert AUDUSD.pip_size == 0.0001
    assert AUDUSD.tick_size == 0.00001
    assert AUDUSD.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert AUDUSD.price_decimals == 5
