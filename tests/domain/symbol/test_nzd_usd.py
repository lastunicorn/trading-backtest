"""Tests for `NzdUsd`'s frozen specification."""

from domain.symbol import NzdUsd, Symbol


def test_is_a_symbol() -> None:
    assert isinstance(NzdUsd(), Symbol)


def test_specification() -> None:
    nzd_usd = NzdUsd()
    assert nzd_usd.name == "New Zealand Dollar / U.S. Dollar"
    assert nzd_usd.ticker == "NZDUSD"
    assert nzd_usd.pip_size == 0.0001
    assert nzd_usd.tick_size == 0.00001


def test_price_decimals() -> None:
    assert NzdUsd().price_decimals == 5
