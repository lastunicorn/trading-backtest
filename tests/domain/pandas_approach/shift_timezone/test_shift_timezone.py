"""Tests for `domain.pandas_approach.shift_timezone.shift_timezone`."""

from zoneinfo import ZoneInfo

import pandas as pd

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
    frame = pd.DataFrame({"datetime": pd.to_datetime(["2026-01-15 09:00"])})

    result = shift_timezone(frame, UTC)

    assert result["datetime"].iloc[0] == pd.Timestamp("2026-01-15 14:00")


def test_other_columns_pass_through_unchanged() -> None:
    frame = pd.DataFrame({
        "datetime": pd.to_datetime(["2026-01-15 09:00"]),
        "close": [1.23456],
    })

    result = shift_timezone(frame, LONDON, from_tz=NEW_YORK)

    assert result["close"].iloc[0] == 1.23456
