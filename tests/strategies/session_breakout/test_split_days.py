"""Tests for `strategies.session_breakout.SessionBreakout.split_days`."""

from strategies.session_breakout import SessionBreakout

from ._fakes import FLAT, TUESDAY, WEDNESDAY, data, day_frame


def test_every_day_with_a_usable_session() -> None:
    days = SessionBreakout().split_days(data(day_frame(TUESDAY), day_frame(WEDNESDAY)))

    assert days == [TUESDAY, WEDNESDAY]


def test_a_day_cancelled_by_its_range_still_counts() -> None:
    # Tuning max_range_pips must not move the split boundaries.
    days = SessionBreakout(max_range_pips=5).split_days(data(day_frame(TUESDAY)))

    assert days == [TUESDAY]


def test_a_day_without_session_bars_is_left_out() -> None:
    days = SessionBreakout().split_days(data(day_frame(TUESDAY, drop_before="09:00"), day_frame(WEDNESDAY)))

    assert days == [WEDNESDAY]


def test_a_flat_session_is_left_out() -> None:
    days = SessionBreakout().split_days(data(day_frame(TUESDAY, session=FLAT), day_frame(WEDNESDAY)))

    assert days == [WEDNESDAY]
