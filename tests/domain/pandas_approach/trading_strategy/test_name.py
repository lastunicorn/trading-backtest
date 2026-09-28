"""Tests for `domain.pandas_approach.trading_strategy.TradingStrategy.name`."""

from ._fakes import DataclassStrategy, PlainStrategy


def test_defaults_to_the_class_name() -> None:
    assert DataclassStrategy().name == "DataclassStrategy"
    assert PlainStrategy().name == "PlainStrategy"


def test_can_be_overridden() -> None:
    class Named(PlainStrategy):
        @property
        def name(self) -> str:
            return "Narrow Asia Fade"

    assert Named().name == "Narrow Asia Fade"
