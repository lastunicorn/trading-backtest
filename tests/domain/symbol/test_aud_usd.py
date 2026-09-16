"""Tests for `AudUsd`'s frozen specification."""

from domain.symbol import AudUsd, Symbol


def test_is_a_symbol() -> None:
    assert isinstance(AudUsd(), Symbol)


def test_specification() -> None:
    aud_usd = AudUsd()
    assert aud_usd.name == "Australian Dollar / U.S. Dollar"
    assert aud_usd.ticker == "AUDUSD"
    assert aud_usd.pip_size == 0.0001
    assert aud_usd.tick_size == 0.00001


def test_price_decimals() -> None:
    assert AudUsd().price_decimals == 5
