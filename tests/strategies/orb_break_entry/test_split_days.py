"""Tests for `strategies.orb_break_entry.OrbBreakEntry.split_days`."""

from datetime import time
from zoneinfo import ZoneInfo

from domain.broker_clock import BROKER_SERVER_TZ
from domain.trading_session import TradingSession
from strategies.orb_break_entry import OrbBreakEntry

from ._fakes import FLAT, QUIET, TUESDAY, WEDNESDAY, data, day_frame, range_at


def test_every_date_with_a_usable_opening_range() -> None:
    days = OrbBreakEntry().split_days(data(day_frame(TUESDAY), day_frame(WEDNESDAY)))

    assert days == [TUESDAY, WEDNESDAY]


def test_a_date_without_a_break_still_counts() -> None:
    # The fakes' quiet bars never reach the range, so neither day trades.
    assert OrbBreakEntry().generate_positions(data(day_frame(TUESDAY))) == []
    assert OrbBreakEntry().split_days(data(day_frame(TUESDAY))) == [TUESDAY]


def test_a_date_without_range_bars_is_left_out() -> None:
    days = OrbBreakEntry().split_days(data(day_frame(TUESDAY, drop=("09:30", "09:45")), day_frame(WEDNESDAY)))

    assert days == [WEDNESDAY]


def test_a_flat_range_is_left_out() -> None:
    days = OrbBreakEntry().split_days(data(day_frame(TUESDAY, range_bar=FLAT), day_frame(WEDNESDAY)))

    assert days == [WEDNESDAY]


def test_dates_are_new_york_dates_whatever_the_data_clock() -> None:
    # On the broker clock (New York + 7h) a New York date's evening bars are dated the next day.
    days = OrbBreakEntry().split_days(data(day_frame(TUESDAY), day_frame(WEDNESDAY), timezone=BROKER_SERVER_TZ))

    assert days == [TUESDAY, WEDNESDAY]


def test_dates_are_in_the_session_start_zone() -> None:
    # 09:00 Tokyo is 19:00 ET the evening before: Tuesday evening's range is Tokyo's Wednesday.
    tokyo = ZoneInfo("Asia/Tokyo")
    session = TradingSession(time(9, 0, tzinfo=tokyo), time(15, 0, tzinfo=tokyo))

    days = OrbBreakEntry(session=session).split_days(data(day_frame(TUESDAY, range_bar=QUIET,
                                                                    overrides=range_at("19:00"))))

    assert days == [WEDNESDAY]
