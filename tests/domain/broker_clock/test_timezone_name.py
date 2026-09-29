"""Tests for `domain.broker_clock.timezone_name`."""

from datetime import timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ, timezone_by_name, timezone_name


def test_broker_server_clock_is_broker() -> None:
    assert timezone_name(BROKER_SERVER_TZ) == "broker"


def test_zoneinfo_is_its_iana_key() -> None:
    assert timezone_name(ZoneInfo("Europe/London")) == "Europe/London"


@pytest.mark.parametrize("name", ["broker", "UTC", "America/New_York"])
def test_reads_back_through_timezone_by_name(name: str) -> None:
    assert timezone_name(timezone_by_name(name)) == name


def test_a_fixed_offset_is_displayed_as_str() -> None:
    assert timezone_name(timezone(timedelta(hours=2))) == "UTC+02:00"
