"""Tests for `domain.pandas_approach.trading_strategy.TradingStrategy.parameters`."""

from ._fakes import DataclassStrategy, PlainStrategy


def test_dataclass_strategy_reports_its_fields() -> None:
    assert DataclassStrategy(rel_vol_min=2.0).parameters() == {"threshold_pips": 21.72, "rel_vol_min": 2.0}


def test_plain_strategy_reports_nothing() -> None:
    assert PlainStrategy().parameters() == {}
