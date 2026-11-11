"""Tests for `NZDUSD`'s frozen specification."""

from domain.market_data.symbol import NZDUSD, SymbolCategory


def test_specification() -> None:
    assert NZDUSD.name == "New Zealand Dollar / U.S. Dollar"
    assert NZDUSD.ticker == "NZDUSD"
    assert NZDUSD.pip_size == 0.0001
    assert NZDUSD.tick_size == 0.00001
    assert NZDUSD.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert NZDUSD.price_decimals == 5
