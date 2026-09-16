"""Tests for `XauUsd`'s frozen specification.

Values follow the common MT5 default for gold (2-decimal quote, pip = 0.1,
tick = 0.01) -- metals have no cross-broker-standard pip the way FX pairs do,
see the note in `domain.symbol.XauUsd`.
"""

import pytest

from domain.symbol import Symbol, SymbolCategory, XauUsd


def test_is_a_symbol() -> None:
    assert isinstance(XauUsd(), Symbol)


def test_specification() -> None:
    xau_usd = XauUsd()
    assert xau_usd.name == "Gold / U.S. Dollar"
    assert xau_usd.ticker == "XAUUSD"
    assert xau_usd.pip_size == 0.1
    assert xau_usd.tick_size == 0.01
    assert xau_usd.category == SymbolCategory.COMMODITY


def test_price_decimals() -> None:
    assert XauUsd().price_decimals == 2


def test_to_pips_uses_the_gold_pip_size() -> None:
    assert XauUsd().to_pips(1.5) == pytest.approx(15.0)
