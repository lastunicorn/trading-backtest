"""Tests for `strategies.orb_break_entry.OrbBreakEntry.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from strategies.orb_break_entry import OrbBreakEntry

NEW_YORK = ZoneInfo("America/New_York")


def _ny(hour: int, minute: int = 0) -> time:
    return time(hour, minute, tzinfo=NEW_YORK)


def test_defaults_match_the_description() -> None:
    strategy = OrbBreakEntry()

    assert (strategy.range_start, strategy.range_end) == (_ny(9, 30), _ny(9, 45))
    assert strategy.orders_expire == _ny(11, 30)
    assert strategy.exit_at == _ny(16, 0)
    assert strategy.risk_reward == 2.0


@pytest.mark.parametrize("risk_reward", [0, -1])
def test_non_positive_risk_reward_is_rejected(risk_reward: float) -> None:
    with pytest.raises(ValueError, match="risk_reward"):
        OrbBreakEntry(risk_reward=risk_reward)


@pytest.mark.parametrize("name", ["range_start", "range_end", "orders_expire", "exit_at"])
def test_a_bound_without_a_timezone_is_rejected(name: str) -> None:
    bound = getattr(OrbBreakEntry(), name).replace(tzinfo=None)

    with pytest.raises(ValueError, match=f"{name} must carry a timezone"):
        OrbBreakEntry(**{name: bound})


@pytest.mark.parametrize("bounds", [
    {"range_end": _ny(9, 30)},                         # empty range
    {"range_end": _ny(9, 15)},                         # range ends before it starts
    {"orders_expire": _ny(9, 40)},                     # orders expire inside the range
])
def test_bounds_out_of_order_are_rejected(bounds: dict) -> None:
    with pytest.raises(ValueError, match="range_start < range_end <= orders_expire"):
        OrbBreakEntry(**bounds)


@pytest.mark.parametrize("exit_at", [_ny(11, 30), _ny(10, 0)])
def test_exit_at_not_after_the_orders_expire_is_rejected(exit_at: time) -> None:
    with pytest.raises(ValueError, match="exit_at"):
        OrbBreakEntry(exit_at=exit_at)


def test_no_time_stop_is_accepted() -> None:
    assert OrbBreakEntry(exit_at=None).exit_at is None


def test_orders_may_expire_when_the_range_ends() -> None:
    OrbBreakEntry(orders_expire=_ny(9, 45))


def test_bounds_may_be_in_different_zones() -> None:
    # 16:30 on the broker clock is 09:30 New York, always.
    OrbBreakEntry(range_start=time(16, 30, tzinfo=BROKER_SERVER_TZ))
