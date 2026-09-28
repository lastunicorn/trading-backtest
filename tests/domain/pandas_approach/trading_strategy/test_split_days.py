"""Tests for `domain.pandas_approach.trading_strategy.TradingStrategy.split_days`."""

from datetime import date

from ._fakes import PlainStrategy, data_over


def test_defaults_to_every_calendar_day_with_a_bar_once() -> None:
    data = data_over(["2026-01-05 10:00", "2026-01-05 10:05", "2026-01-07 00:00"])

    assert sorted(PlainStrategy().split_days(data)) == [date(2026, 1, 5), date(2026, 1, 7)]
