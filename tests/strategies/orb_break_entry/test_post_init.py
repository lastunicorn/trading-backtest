"""Tests for `strategies.orb_break_entry.OrbBreakEntry.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from domain.trading_session import LONDON_SESSION, NEW_YORK_SESSION, TradingSession
from strategies.orb_break_entry import OrbBreakEntry

NEW_YORK = ZoneInfo("America/New_York")


def test_defaults_match_the_description() -> None:
    strategy = OrbBreakEntry()

    assert strategy.session == NEW_YORK_SESSION    # 09:30-16:00 ET
    assert (strategy.range_minutes, strategy.orders_minutes) == (15, 120)
    assert strategy.exit_at_session_end is True
    assert strategy.risk_reward == 2.0


@pytest.mark.parametrize("risk_reward", [0, -1])
def test_non_positive_risk_reward_is_rejected(risk_reward: float) -> None:
    with pytest.raises(ValueError, match="risk_reward"):
        OrbBreakEntry(risk_reward=risk_reward)


@pytest.mark.parametrize("name", ["range_minutes", "orders_minutes"])
@pytest.mark.parametrize("minutes", [0, -15])
def test_non_positive_minutes_are_rejected(name: str, minutes: int) -> None:
    with pytest.raises(ValueError, match=f"{name} must be positive"):
        OrbBreakEntry(**{name: minutes})


@pytest.mark.parametrize("bounds", [
    {"orders_minutes": 10},                            # orders expire inside the range
    {"range_minutes": 121},                            # range runs past 11:30
])
def test_a_range_ending_after_the_orders_expire_is_rejected(bounds: dict) -> None:
    with pytest.raises(ValueError, match="must end by the orders' expiry"):
        OrbBreakEntry(**bounds)


@pytest.mark.parametrize("orders_minutes", [390, 400])    # 16:00 ET, the session's end, and after it
def test_orders_expiring_at_or_after_the_session_end_are_rejected(orders_minutes: int) -> None:
    with pytest.raises(ValueError, match="before the New York session end"):
        OrbBreakEntry(orders_minutes=orders_minutes)


def test_the_check_holds_without_a_time_stop() -> None:
    with pytest.raises(ValueError, match="session end"):
        OrbBreakEntry(orders_minutes=400, exit_at_session_end=False)


def test_orders_may_expire_when_the_range_ends() -> None:
    OrbBreakEntry(orders_minutes=15)
    OrbBreakEntry(range_minutes=120)


def test_any_session_is_accepted() -> None:
    assert OrbBreakEntry(session=LONDON_SESSION).session == LONDON_SESSION


def test_session_bounds_may_be_in_different_zones() -> None:
    # 16:30 on the broker clock is 09:30 New York, always.
    OrbBreakEntry(session=TradingSession(time(16, 30, tzinfo=BROKER_SERVER_TZ), time(16, 0, tzinfo=NEW_YORK)))


def test_a_session_past_midnight_ends_the_next_day() -> None:
    # 22:00-02:00 ET: the orders' 23:30 expiry is before the 02:00 end, the next day.
    OrbBreakEntry(session=TradingSession(time(22, 0, tzinfo=NEW_YORK), time(2, 0, tzinfo=NEW_YORK)))
