"""Tests for `TradingSessionTemplate.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.trading_session_template import TradingSessionTemplate

LONDON = ZoneInfo("Europe/London")


def test_naive_start_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        TradingSessionTemplate(start_time=time(8, 0), end_time=time(16, 0, tzinfo=LONDON))


def test_naive_end_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        TradingSessionTemplate(start_time=time(8, 0, tzinfo=LONDON), end_time=time(16, 0))


def test_both_tz_aware_is_accepted() -> None:
    template = TradingSessionTemplate(
        start_time=time(8, 0, tzinfo=LONDON),
        end_time=time(16, 0, tzinfo=LONDON),
    )
    assert template.start_time.tzinfo is LONDON
    assert template.end_time.tzinfo is LONDON
