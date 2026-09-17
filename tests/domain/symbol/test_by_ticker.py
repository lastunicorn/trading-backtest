"""Tests for `domain.symbol.by_ticker`."""

import pytest

from domain.symbol import EurUsd, by_ticker


def test_finds_symbol_by_ticker() -> None:
    assert by_ticker("EURUSD") == EurUsd()


def test_is_case_insensitive() -> None:
    assert by_ticker("eurusd") == EurUsd()


def test_raises_for_unknown_ticker() -> None:
    with pytest.raises(ValueError, match="FOOBAR"):
        by_ticker("FOOBAR")
