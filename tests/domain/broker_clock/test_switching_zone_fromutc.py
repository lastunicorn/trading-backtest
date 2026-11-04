"""Tests for `domain.broker_clock.SwitchingZone.fromutc` (via `datetime.astimezone`), on `HISTDATA_TZ`."""

from datetime import datetime

from domain.broker_clock import HISTDATA_TZ

from ._fakes import NEW_YORK, UTC


def test_new_york_sunday_17_00_opens_the_week_at_17_00_before_2019() -> None:
    ny_open = datetime(2018, 3, 18, 17, 0, tzinfo=NEW_YORK)   # mismatch week

    assert ny_open.astimezone(HISTDATA_TZ).replace(tzinfo=None) == datetime(2018, 3, 18, 17, 0)


def test_new_york_sunday_17_00_opens_a_mismatch_week_at_16_00_from_2019() -> None:
    ny_open = datetime(2019, 3, 17, 17, 0, tzinfo=NEW_YORK)

    assert ny_open.astimezone(HISTDATA_TZ).replace(tzinfo=None) == datetime(2019, 3, 17, 16, 0)


def test_round_trips_through_utc_around_the_switch() -> None:
    for wall in (datetime(2018, 12, 31, 23, 59), datetime(2019, 1, 1, 0, 0), datetime(2018, 3, 19), datetime(2019, 3, 18)):
        back = wall.replace(tzinfo=HISTDATA_TZ).astimezone(UTC).astimezone(HISTDATA_TZ)

        assert back.replace(tzinfo=None) == wall
        assert back.tzinfo is HISTDATA_TZ
