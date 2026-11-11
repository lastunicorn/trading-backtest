"""Tests for `domain.backtesting.trading_strategy.TradingStrategy.parameters`."""

from domain.market_data.trading_session import LONDON_SESSION

from ._fakes import DataclassStrategy, PlainStrategy, SessionStrategy


def test_dataclass_strategy_reports_its_fields() -> None:
    assert DataclassStrategy(rel_vol_min=2.0).parameters() == {"threshold_pips": 21.72, "rel_vol_min": 2.0}


def test_plain_strategy_reports_nothing() -> None:
    assert PlainStrategy().parameters() == {}


def test_a_dataclass_field_stays_an_object() -> None:
    assert SessionStrategy(session=LONDON_SESSION).parameters() == {"session": LONDON_SESSION}
