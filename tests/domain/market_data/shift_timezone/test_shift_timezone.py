"""Tests for `domain.market_data.shift_timezone.shift_timezone`."""

from zoneinfo import ZoneInfo

import pandas as pd

from domain.market_data.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ
from domain.market_data.shift_timezone import shift_timezone

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


def test_a_switching_zone_converts_each_row_by_the_rules_in_force_then() -> None:
    # Mismatch weeks: histdata is New York time in 2018 (UTC-4), London - 5h from 2019 (UTC-5).
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2019-03-18 00:00", "2018-03-19 00:00"])}, index=[7, 3])

    result = shift_timezone(frame, UTC, from_tz=HISTDATA_TZ)

    assert list(result.index) == [7, 3]
    assert list(result["datetime"]) == [pd.Timestamp("2019-03-18 05:00"), pd.Timestamp("2018-03-19 04:00")]


def test_a_switching_zone_round_trips() -> None:
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2018-03-19 00:00", "2018-12-31 23:59", "2019-01-01 00:00",
                                                      "2019-03-18 00:00"])})

    back = shift_timezone(shift_timezone(frame, UTC, from_tz=HISTDATA_TZ), HISTDATA_TZ, from_tz=UTC)

    assert list(back["datetime"]) == list(frame["datetime"])


def test_a_switching_zone_reads_a_reading_only_the_other_side_lacks() -> None:
    # 02:30 on 2019-03-10 doesn't exist in New York (spring forward), but histdata is London - 5h by then.
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2019-03-10 02:30"])})

    assert shift_timezone(frame, UTC, from_tz=HISTDATA_TZ)["datetime"].iat[0] == pd.Timestamp("2019-03-10 07:30")
