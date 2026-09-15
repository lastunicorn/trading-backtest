"""Tests for `NewYorkSessionTemplate`'s frozen defaults and its DST-dependent
UTC window."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from domain.trading_session_template import NewYorkSessionTemplate

NEW_YORK = ZoneInfo("America/New_York")

# Dates safely inside (not near the edges of) a DST period, so the exact
# transition day doesn't matter -- only that one is winter and one is summer.
WINTER_DATE = date(2026, 1, 15)
SUMMER_DATE = date(2026, 7, 15)


def test_defaults() -> None:
    template = NewYorkSessionTemplate()
    assert template.start_time == time(9, 30, tzinfo=NEW_YORK)
    assert template.end_time == time(16, 0, tzinfo=NEW_YORK)


def test_est_window_matches_docstring() -> None:
    # 14:30-21:00 UTC under EST, per the class docstring.
    template = NewYorkSessionTemplate()
    session = template.create_session(WINTER_DATE)

    assert session.start_dt_utc() == datetime(2026, 1, 15, 14, 30, tzinfo=UTC)
    assert session.end_dt_utc() == datetime(2026, 1, 15, 21, 0, tzinfo=UTC)


def test_edt_window_matches_docstring() -> None:
    # 13:30-20:00 UTC under EDT, per the class docstring.
    template = NewYorkSessionTemplate()
    session = template.create_session(SUMMER_DATE)

    assert session.start_dt_utc() == datetime(2026, 7, 15, 13, 30, tzinfo=UTC)
    assert session.end_dt_utc() == datetime(2026, 7, 15, 20, 0, tzinfo=UTC)
