"""Tests for `domain.broker_clock.ShiftedZone.fromutc` (via `datetime.astimezone`)."""

from datetime import datetime

from domain.broker_clock import BROKER_SERVER_TZ

from ._fakes import MISMATCH, NEW_YORK, SUMMER, UTC, WINTER


def test_new_york_sunday_17_00_is_server_monday_00_00_all_year() -> None:
    for server_open in (WINTER, SUMMER, MISMATCH):
        ny_open = datetime(server_open.year, server_open.month, server_open.day - 1, 17, 0, tzinfo=NEW_YORK)

        assert ny_open.astimezone(BROKER_SERVER_TZ).replace(tzinfo=None) == server_open


def test_round_trips_through_utc() -> None:
    for server_time in (WINTER, SUMMER, MISMATCH):
        aware = server_time.replace(tzinfo=BROKER_SERVER_TZ)

        back = aware.astimezone(UTC).astimezone(BROKER_SERVER_TZ)

        assert back.replace(tzinfo=None) == server_time
        assert back.tzinfo is BROKER_SERVER_TZ


def test_to_utc() -> None:
    assert WINTER.replace(tzinfo=BROKER_SERVER_TZ).astimezone(UTC) == datetime(2020, 1, 5, 22, 0, tzinfo=UTC)
    assert SUMMER.replace(tzinfo=BROKER_SERVER_TZ).astimezone(UTC) == datetime(2020, 7, 5, 21, 0, tzinfo=UTC)
