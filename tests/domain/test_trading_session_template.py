"""Unit tests for `domain.trading_session_template`.

Run from the repo root with `python3 -m pytest tests/` (the `-m` form puts the
repo root on `sys.path` so `from domain...` imports resolve, matching how the
pipeline CLIs are already run from any cwd).
"""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from domain.trading_session_template import (
    LondonSessionTemplate,
    NewYorkSessionTemplate,
    TokyoSessionTemplate,
    TradingSessionTemplate,
)

TOKYO = ZoneInfo("Asia/Tokyo")
LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")

# Dates safely inside (not near the edges of) a DST period, so the exact
# transition day doesn't matter -- only that one is winter and one is summer.
WINTER_DATE = date(2026, 1, 15)
SUMMER_DATE = date(2026, 7, 15)


class TestPostInit:
    def test_naive_start_time_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            TradingSessionTemplate(start_time=time(8, 0), end_time=time(16, 0, tzinfo=LONDON))

    def test_naive_end_time_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            TradingSessionTemplate(start_time=time(8, 0, tzinfo=LONDON), end_time=time(16, 0))

    def test_both_tz_aware_is_accepted(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 0, tzinfo=LONDON),
        )
        assert template.start_time.tzinfo is LONDON
        assert template.end_time.tzinfo is LONDON


class TestLocalTimeOn:
    def test_start_time_on_combines_date_and_local_time(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        assert template.start_time_on(WINTER_DATE) == datetime(2026, 1, 15, 8, 0, tzinfo=LONDON)

    def test_end_time_on_combines_date_and_local_time(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        assert template.end_time_on(WINTER_DATE) == datetime(2026, 1, 15, 16, 30, tzinfo=LONDON)


class TestUtcConversion:
    def test_start_time_utc_on_under_gmt(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        assert template.start_time_utc_on(WINTER_DATE) == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)

    def test_start_time_utc_on_under_bst(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        # BST is UTC+1, so the same local clock time is an hour earlier in UTC.
        assert template.start_time_utc_on(SUMMER_DATE) == datetime(2026, 7, 15, 7, 0, tzinfo=UTC)

    def test_end_time_utc_on_under_gmt(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        assert template.end_time_utc_on(WINTER_DATE) == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)

    def test_end_time_utc_on_under_bst(self) -> None:
        template = TradingSessionTemplate(
            start_time=time(8, 0, tzinfo=LONDON),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        assert template.end_time_utc_on(SUMMER_DATE) == datetime(2026, 7, 15, 15, 30, tzinfo=UTC)


class TestCreateSession:
    def test_non_wrapping_session_keeps_the_same_calendar_date(self) -> None:
        template = LondonSessionTemplate()
        session = template.create_session(WINTER_DATE)

        assert session.start_dt_utc() == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
        assert session.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)

    def test_session_crossing_midnight_rolls_end_to_the_next_day(self) -> None:
        # Same tz on both ends keeps the arithmetic obvious: 23:00 -> 01:00 UTC
        # can only make sense as a 2-hour window into the next day.
        template = TradingSessionTemplate(
            start_time=time(23, 0, tzinfo=UTC),
            end_time=time(1, 0, tzinfo=UTC),
        )
        session = template.create_session(WINTER_DATE)

        assert session.start_dt_utc() == datetime(2026, 1, 15, 23, 0, tzinfo=UTC)
        assert session.end_dt_utc() == datetime(2026, 1, 16, 1, 0, tzinfo=UTC)

    def test_session_with_different_start_and_end_zones(self) -> None:
        # Asia start paired with a London end, per the module docstring --
        # the wrap decision has to compare UTC instants, since "09:00" and
        # "16:30" as bare local times carry no meaningful order across zones.
        template = TradingSessionTemplate(
            start_time=time(9, 0, tzinfo=TOKYO),
            end_time=time(16, 30, tzinfo=LONDON),
        )
        session = template.create_session(WINTER_DATE)

        assert session.start_dt_utc() == datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        assert session.end_dt_utc() == datetime(2026, 1, 15, 16, 30, tzinfo=UTC)


class TestTokyoSessionTemplate:
    def test_defaults(self) -> None:
        template = TokyoSessionTemplate()
        assert template.start_time == time(9, 0, tzinfo=TOKYO)
        assert template.end_time == time(15, 30, tzinfo=TOKYO)

    def test_no_dst_so_utc_offset_is_constant(self) -> None:
        template = TokyoSessionTemplate()
        winter_start = template.start_time_utc_on(WINTER_DATE)
        summer_start = template.start_time_utc_on(SUMMER_DATE)

        assert winter_start.timetz() == summer_start.timetz()


class TestLondonSessionTemplate:
    def test_defaults(self) -> None:
        template = LondonSessionTemplate()
        assert template.start_time == time(8, 0, tzinfo=LONDON)
        assert template.end_time == time(16, 30, tzinfo=LONDON)


class TestNewYorkSessionTemplate:
    def test_defaults(self) -> None:
        template = NewYorkSessionTemplate()
        assert template.start_time == time(9, 30, tzinfo=NEW_YORK)
        assert template.end_time == time(16, 0, tzinfo=NEW_YORK)

    def test_est_window_matches_docstring(self) -> None:
        # 14:30-21:00 UTC under EST, per the class docstring.
        template = NewYorkSessionTemplate()
        session = template.create_session(WINTER_DATE)

        assert session.start_dt_utc() == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
        assert session.end_dt_utc() == datetime(2026, 1, 15, 21, 0, tzinfo=UTC)

    def test_edt_window_matches_docstring(self) -> None:
        # 13:30-20:00 UTC under EDT, per the class docstring.
        template = NewYorkSessionTemplate()
        session = template.create_session(SUMMER_DATE)

        assert session.start_dt_utc() == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
        assert session.end_dt_utc() == datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
