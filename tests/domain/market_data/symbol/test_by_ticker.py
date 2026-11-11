"""Tests for `domain.market_data.symbol.by_ticker`."""

import pytest

from domain.market_data.symbol import EURUSD, get_symbol_by_ticker


def test_finds_symbol_by_ticker() -> None:
    assert get_symbol_by_ticker("EURUSD") == EURUSD


def test_is_case_insensitive() -> None:
    assert get_symbol_by_ticker("eurusd") == EURUSD


def test_raises_for_unknown_ticker() -> None:
    with pytest.raises(ValueError, match="FOOBAR"):
        get_symbol_by_ticker("FOOBAR")
