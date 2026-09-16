"""Tests for `XagUsd`'s frozen specification.

Silver commonly quotes one decimal deeper than gold (3 vs 2) -- see the note
in `domain.symbol.XauUsd` on metals having no cross-broker-standard pip.
"""

import pytest

from domain.symbol import Symbol, SymbolCategory, XagUsd


def test_is_a_symbol() -> None:
    assert isinstance(XagUsd(), Symbol)


def test_specification() -> None:
    xag_usd = XagUsd()
    assert xag_usd.name == "Silver / U.S. Dollar"
    assert xag_usd.ticker == "XAGUSD"
    assert xag_usd.pip_size == 0.01
    assert xag_usd.tick_size == 0.001
    assert xag_usd.category == SymbolCategory.COMMODITY


def test_price_decimals() -> None:
    assert XagUsd().price_decimals == 3


def test_to_pips_uses_the_silver_pip_size() -> None:
    assert XagUsd().to_pips(0.15) == pytest.approx(15.0)
