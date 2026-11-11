"""Tests for `DEUIDXEUR`'s frozen specification.

The German 40 Index (the DAX) as Dukascopy quotes it: 3 decimals, and a
"pip" of one index point -- see the note in `domain.market_data.symbol.DEUIDXEUR`.
"""

import pytest

from domain.market_data.symbol import DEUIDXEUR, SymbolCategory


def test_specification() -> None:
    assert DEUIDXEUR.name == "German 40 Index"
    assert DEUIDXEUR.ticker == "DEUIDXEUR"
    assert DEUIDXEUR.pip_size == 1.0
    assert DEUIDXEUR.tick_size == 0.001
    assert DEUIDXEUR.category == SymbolCategory.INDEX


def test_price_decimals() -> None:
    assert DEUIDXEUR.price_decimals == 3


def test_to_pips_counts_index_points() -> None:
    assert DEUIDXEUR.to_pips(12.5) == pytest.approx(12.5)
