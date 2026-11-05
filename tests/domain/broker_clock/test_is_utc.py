"""Tests for `domain.broker_clock.is_utc`."""

from datetime import UTC, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ, is_utc


@pytest.mark.parametrize("zone", [UTC, ZoneInfo("UTC"), ZoneInfo("Etc/UTC")])
def test_utc_zones_are_utc(zone) -> None:
    assert is_utc(zone)


@pytest.mark.parametrize("zone", [BROKER_SERVER_TZ, HISTDATA_TZ, timezone(timedelta(hours=2))])
def test_offset_zones_are_not_utc(zone) -> None:
    assert not is_utc(zone)


def test_a_zone_at_utc_only_in_winter_is_not_utc() -> None:
    assert not is_utc(ZoneInfo("Europe/London"))
