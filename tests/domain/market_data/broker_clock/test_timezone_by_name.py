"""Tests for `domain.market_data.broker_clock.timezone_by_name`."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pytest

from domain.market_data.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ, timezone_by_name


@pytest.mark.parametrize("name", ["broker", "BROKER", " Broker "])
def test_broker_is_the_broker_server_clock(name: str) -> None:
    assert timezone_by_name(name) is BROKER_SERVER_TZ


@pytest.mark.parametrize("name", ["histdata", "HISTDATA", " Histdata "])
def test_histdata_is_the_histdata_clock(name: str) -> None:
    assert timezone_by_name(name) is HISTDATA_TZ


def test_iana_names_are_zoneinfo() -> None:
    assert timezone_by_name("Europe/London") == ZoneInfo("Europe/London")


def test_unknown_name_raises_like_zoneinfo() -> None:
    with pytest.raises(ZoneInfoNotFoundError):
        timezone_by_name("Mars/Olympus_Mons")
