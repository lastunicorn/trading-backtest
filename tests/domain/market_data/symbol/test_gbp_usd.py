"""Tests for `GBPUSD`'s frozen specification."""

from domain.market_data.symbol import GBPUSD, SymbolCategory


def test_specification() -> None:
    assert GBPUSD.name == "British Pound / U.S. Dollar"
    assert GBPUSD.ticker == "GBPUSD"
    assert GBPUSD.pip_size == 0.0001
    assert GBPUSD.tick_size == 0.00001
    assert GBPUSD.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert GBPUSD.price_decimals == 5
