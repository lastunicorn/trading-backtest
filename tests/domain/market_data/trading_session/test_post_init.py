"""Tests for `TradingSession.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.market_data.trading_session import TradingSession

LONDON = ZoneInfo("Europe/London")


def test_naive_start_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        TradingSession(start_time=time(8, 0), end_time=time(16, 0, tzinfo=LONDON))


def test_naive_end_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        TradingSession(start_time=time(8, 0, tzinfo=LONDON), end_time=time(16, 0))


def test_both_tz_aware_is_accepted() -> None:
    session = TradingSession(
        start_time=time(8, 0, tzinfo=LONDON),
        end_time=time(16, 0, tzinfo=LONDON),
    )
    assert session.start_time.tzinfo is LONDON
    assert session.end_time.tzinfo is LONDON
