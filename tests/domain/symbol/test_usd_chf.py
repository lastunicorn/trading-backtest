"""Tests for `UsdChf`'s frozen specification."""

from domain.symbol import Symbol, UsdChf


def test_is_a_symbol() -> None:
    assert isinstance(UsdChf(), Symbol)


def test_specification() -> None:
    usd_chf = UsdChf()
    assert usd_chf.name == "U.S. Dollar / Swiss Franc"
    assert usd_chf.ticker == "USDCHF"
    assert usd_chf.pip_size == 0.0001
    assert usd_chf.tick_size == 0.00001


def test_price_decimals() -> None:
    assert UsdChf().price_decimals == 5
