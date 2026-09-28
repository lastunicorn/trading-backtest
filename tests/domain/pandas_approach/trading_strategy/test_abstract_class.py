"""`TradingStrategy` cannot be instantiated directly -- `generate_positions` is abstract."""

import pytest

from domain.pandas_approach.trading_strategy import TradingStrategy


def test_cannot_be_instantiated_directly() -> None:
    with pytest.raises(TypeError):
        TradingStrategy()


def test_subclass_without_generate_positions_cannot_be_instantiated() -> None:
    class Incomplete(TradingStrategy):
        pass

    with pytest.raises(TypeError):
        Incomplete()
