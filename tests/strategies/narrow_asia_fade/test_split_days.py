"""Tests for `strategies.narrow_asia_fade.NarrowAsiaFade.split_days`."""

from datetime import date

from strategies.narrow_asia_fade import NarrowAsiaFade

from ._fakes import MONDAY, data, day_frame


def test_weekdays_with_a_usable_asia_session() -> None:
    tuesday = date(2026, 1, 6)

    assert NarrowAsiaFade().split_days(data(day_frame(MONDAY), day_frame(tuesday))) == [MONDAY, tuesday]


def test_wide_asia_days_still_count() -> None:
    wide = (1.1000, 1.1030, 1.0995, 1.1000, 10)

    assert NarrowAsiaFade().split_days(data(day_frame(overrides={"05:00": wide}))) == [MONDAY]


def test_days_missing_too_many_asia_bars_are_left_out() -> None:
    thin = day_frame(date(2026, 1, 6), drop=["03:00", "04:00", "05:00", "06:00"])

    assert NarrowAsiaFade().split_days(data(day_frame(MONDAY), thin)) == [MONDAY]


def test_weekends_are_left_out() -> None:
    assert NarrowAsiaFade().split_days(data(day_frame(MONDAY), day_frame(date(2026, 1, 10)))) == [MONDAY]
