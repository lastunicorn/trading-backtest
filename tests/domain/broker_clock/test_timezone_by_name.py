"""Tests for `domain.broker_clock.timezone_by_name`."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from domain.broker_clock import BROKER_SERVER_TZ, timezone_by_name


@pytest.mark.parametrize("name", ["broker", "BROKER", " Broker "])
def test_broker_is_the_broker_server_clock(name: str) -> None:
    assert timezone_by_name(name) is BROKER_SERVER_TZ


def test_iana_names_are_zoneinfo() -> None:
    assert timezone_by_name("Europe/London") == ZoneInfo("Europe/London")


def test_unknown_name_raises_like_zoneinfo() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        timezone_by_name("Mars/Olympus_Mons")
