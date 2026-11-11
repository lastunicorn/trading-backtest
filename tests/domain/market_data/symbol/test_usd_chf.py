"""Tests for `USDCHF`'s frozen specification."""

from domain.market_data.symbol import SymbolCategory, USDCHF


def test_specification() -> None:
    assert USDCHF.name == "U.S. Dollar / Swiss Franc"
    assert USDCHF.ticker == "USDCHF"
    assert USDCHF.pip_size == 0.0001
    assert USDCHF.tick_size == 0.00001
    assert USDCHF.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert USDCHF.price_decimals == 5
