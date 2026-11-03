"""Tests for `XAGUSD`'s frozen specification.

Silver commonly quotes one decimal deeper than gold (3 vs 2) -- see the note
in `domain.symbol.XAUUSD` on metals having no cross-broker-standard pip.
"""

import pytest

from domain.symbol import SymbolCategory, XAGUSD


def test_specification() -> None:
    assert XAGUSD.name == "Silver / U.S. Dollar"
    assert XAGUSD.ticker == "XAGUSD"
    assert XAGUSD.pip_size == 0.01
    assert XAGUSD.tick_size == 0.001
    assert XAGUSD.category == SymbolCategory.COMMODITY


def test_price_decimals() -> None:
    assert XAGUSD.price_decimals == 3


def test_to_pips_uses_the_silver_pip_size() -> None:
    assert XAGUSD.to_pips(0.15) == pytest.approx(15.0)
