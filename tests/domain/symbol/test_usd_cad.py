"""Tests for `UsdCad`'s frozen specification."""

from domain.symbol import Symbol, SymbolCategory, UsdCad


def test_is_a_symbol() -> None:
    assert isinstance(UsdCad(), Symbol)


def test_specification() -> None:
    usd_cad = UsdCad()
    assert usd_cad.name == "U.S. Dollar / Canadian Dollar"
    assert usd_cad.ticker == "USDCAD"
    assert usd_cad.pip_size == 0.0001
    assert usd_cad.tick_size == 0.00001
    assert usd_cad.category == SymbolCategory.FOREX


def test_price_decimals() -> None:
    assert UsdCad().price_decimals == 5
