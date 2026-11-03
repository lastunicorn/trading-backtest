"""Tests for `domain.symbol.SYMBOLS`, the table of known symbols."""

from domain.symbol import EURUSD, SYMBOLS, USDJPY, XAUUSD


def test_keys_are_the_symbols_tickers() -> None:
    assert all(ticker == symbol.ticker for ticker, symbol in SYMBOLS.items())


def test_holds_every_defined_symbol() -> None:
    assert len(SYMBOLS) == 9
    assert SYMBOLS["EURUSD"] is EURUSD
    assert SYMBOLS["USDJPY"] is USDJPY
    assert SYMBOLS["XAUUSD"] is XAUUSD
