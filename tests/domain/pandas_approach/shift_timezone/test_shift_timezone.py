"""Tests for `domain.pandas_approach.shift_timezone.shift_timezone`."""

from zoneinfo import ZoneInfo

import pandas as pd

from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.shift_timezone import shift_timezone

LONDON = ZoneInfo("Europe/London")
NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def test_converts_naive_wall_clock_between_zones() -> None:
    # 2026-01-15 is winter: EST is UTC-5, GMT is UTC+0.
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-15 09:00"]),
        "close": [1.0],
    })

    result = shift_timezone(frame, UTC, from_tz=NEW_YORK)

    assert result["datetime"].iloc[0] == pd.Timestamp("2026-01-15 14:00")


def test_result_stays_naive() -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2026-01-15 09:00"])})

    result = shift_timezone(frame, UTC, from_tz=NEW_YORK)

    assert result["datetime"].dt.tz is None


def test_defaults_from_tz_to_broker_server_time() -> None:
    # Broker server = New York + 7h: 09:00 server is 02:00 EST, 07:00 UTC.
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2026-01-15 09:00"])})

    result = shift_timezone(frame, UTC)

    assert result["datetime"].iloc[0] == pd.Timestamp("2026-01-15 07:00")


def test_broker_week_open_is_new_york_17_00_sunday_all_year() -> None:
    # Winter, summer, and a week where US and EU daylight saving disagree.
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2020-01-06 00:00", "2020-07-06 00:00", "2020-03-16 00:00"])})

    result = shift_timezone(frame, NEW_YORK, from_tz=BROKER_SERVER_TZ)

    assert result["datetime"].tolist() == pd.to_datetime(
        ["2020-01-05 17:00", "2020-07-05 17:00", "2020-03-15 17:00"]
    ).tolist()


def test_converts_into_the_broker_clock() -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2020-07-05 21:00"])})    # 17:00 EDT

    result = shift_timezone(frame, BROKER_SERVER_TZ, from_tz=UTC)

    assert result["datetime"].iloc[0] == pd.Timestamp("2020-07-06 00:00")


def test_broker_to_broker_is_unchanged() -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2020-03-16 10:35"])})

    result = shift_timezone(frame, BROKER_SERVER_TZ, from_tz=BROKER_SERVER_TZ)

    assert result["datetime"].iloc[0] == pd.Timestamp("2020-03-16 10:35")


def test_other_columns_pass_through_unchanged() -> None:
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-15 09:00"]),
        "close": [1.23456],
    })

    result = shift_timezone(frame, LONDON, from_tz=NEW_YORK)

    assert result["close"].iloc[0] == 1.23456
