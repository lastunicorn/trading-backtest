"""Tests for `XAUUSD`'s frozen specification.

Values follow the common MT5 default for gold (2-decimal quote, pip = 0.1,
tick = 0.01) -- metals have no cross-broker-standard pip the way FX pairs do,
see the note in `domain.market_data.symbol.XAUUSD`.
"""

import pytest

from domain.market_data.symbol import SymbolCategory, XAUUSD


def test_specification() -> None:
    assert XAUUSD.name == "Gold / U.S. Dollar"
    assert XAUUSD.ticker == "XAUUSD"
    assert XAUUSD.pip_size == 0.1
    assert XAUUSD.tick_size == 0.01
    assert XAUUSD.category == SymbolCategory.COMMODITY


def test_price_decimals() -> None:
    assert XAUUSD.price_decimals == 2


def test_to_pips_uses_the_gold_pip_size() -> None:
    assert XAUUSD.to_pips(1.5) == pytest.approx(15.0)
