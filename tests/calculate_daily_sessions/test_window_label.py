"""Tests for `calculate_daily_sessions.window_label`."""

from datetime import time
from zoneinfo import ZoneInfo

from domain.broker_clock import BROKER_SERVER_TZ
from domain.trading_session import ASIA_SESSION, TradingSession
from calculate_daily_sessions import window_label


def test_one_zone_is_named_once() -> None:
    assert window_label(ASIA_SESSION) == "09:00-18:00 Asia/Tokyo"


def test_different_zones_are_named_per_bound() -> None:
    session = TradingSession(time(9, 0, tzinfo=ZoneInfo("Asia/Tokyo")), time(10, 0, tzinfo=BROKER_SERVER_TZ))

    assert window_label(session) == "09:00 Asia/Tokyo - 10:00 broker"
