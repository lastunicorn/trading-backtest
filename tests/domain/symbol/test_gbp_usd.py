"""Tests for `GbpUsd`'s frozen specification."""

from domain.symbol import GbpUsd, Symbol


def test_is_a_symbol() -> None:
    assert isinstance(GbpUsd(), Symbol)


def test_specification() -> None:
    gbp_usd = GbpUsd()
    assert gbp_usd.name == "British Pound / U.S. Dollar"
    assert gbp_usd.ticker == "GBPUSD"
    assert gbp_usd.pip_size == 0.0001
    assert gbp_usd.tick_size == 0.00001


def test_price_decimals() -> None:
    assert GbpUsd().price_decimals == 5
