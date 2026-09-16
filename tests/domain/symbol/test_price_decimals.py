"""Tests for `Symbol.price_decimals`."""

from domain.symbol import Symbol


def _symbol(tick_size: float) -> Symbol:
    return Symbol(name="Test", ticker="TST", pip_size=0.0001, tick_size=tick_size)


def test_counts_decimal_places_from_tick_size() -> None:
    assert _symbol(0.01).price_decimals == 2


def test_handles_tick_sizes_small_enough_for_scientific_notation() -> None:
    # str(0.00001) is "1e-05", not "0.00001" -- a naive
    # str(tick_size).split(".")[1] breaks here; Decimal's exponent doesn't.
    assert _symbol(0.00001).price_decimals == 5


def test_is_computed_once_and_cached() -> None:
    symbol = _symbol(0.01)
    assert "price_decimals" not in symbol.__dict__

    first = symbol.price_decimals
    assert "price_decimals" in symbol.__dict__
    assert symbol.__dict__["price_decimals"] == first
    assert symbol.price_decimals == first
