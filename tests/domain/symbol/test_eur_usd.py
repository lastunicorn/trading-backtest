"""Tests for `EurUsd`'s frozen specification."""

from domain.symbol import EurUsd, Symbol


def test_is_a_symbol() -> None:
    assert isinstance(EurUsd(), Symbol)


def test_specification() -> None:
    eur_usd = EurUsd()
    assert eur_usd.name == "Euro / U.S. Dollar"
    assert eur_usd.ticker == "EURUSD"
    assert eur_usd.pip_size == 0.0001
    assert eur_usd.tick_size == 0.00001


def test_price_decimals() -> None:
    assert EurUsd().price_decimals == 5
