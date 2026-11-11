"""Tests for `EURUSD`'s frozen specification."""

from domain.market_data.symbol import EURUSD, SymbolCategory


def test_specification() -> None:
    assert EURUSD.name == "Euro / U.S. Dollar"
    assert EURUSD.ticker == "EURUSD"
    assert EURUSD.pip_size == 0.0001
    assert EURUSD.tick_size == 0.00001
    assert EURUSD.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert EURUSD.price_decimals == 5
