"""Tests for `strategies.rsi_divergence.RsiDivergence.__post_init__`."""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from strategies.rsi_divergence import RsiDivergence


def test_defaults_match_the_scan_script() -> None:
    strategy = RsiDivergence()

    assert (strategy.rsi_length, strategy.pivot_left, strategy.pivot_right) == (14, 5, 5)
    assert (strategy.range_lower, strategy.range_upper) == (5, 60)
    assert (strategy.rsi_lower, strategy.rsi_upper) == (30, 70)
    assert (strategy.start_time, strategy.end_time) == (None, None)


@pytest.mark.parametrize("risk_reward", [0, -1])
def test_non_positive_risk_reward_is_rejected(risk_reward: float) -> None:
    with pytest.raises(ValueError, match="risk_reward"):
        RsiDivergence(risk_reward=risk_reward)


def test_negative_stop_buffer_is_rejected() -> None:
    with pytest.raises(ValueError, match="stop_buffer_pips"):
        RsiDivergence(stop_buffer_pips=-0.5)


def test_timezone_aware_window_is_accepted() -> None:
    london = ZoneInfo("Europe/London")

    strategy = RsiDivergence(start_time=time(8, 0, tzinfo=london), end_time=time(16, 0, tzinfo=london))

    assert strategy.start_time.tzinfo is london


@pytest.mark.parametrize("field", ["start_time", "end_time"])
def test_window_bound_without_a_timezone_is_rejected(field: str) -> None:
    with pytest.raises(ValueError, match=f"{field} must carry a timezone"):
        RsiDivergence(**{field: time(8, 0)})
