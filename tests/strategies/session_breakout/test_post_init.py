"""Tests for `strategies.session_breakout.SessionBreakout.__post_init__`."""

from datetime import time

import pytest

from strategies.session_breakout import SessionBreakout


def test_defaults_match_the_script() -> None:
    strategy = SessionBreakout()

    # AsianSessionTemplate, and session_breakout_strategy.py's CLI defaults.
    assert (strategy.session_start, strategy.session_end) == (time(9, 0), time(18, 0))
    assert strategy.session_timezone == "Asia/Tokyo"
    assert (strategy.max_range_pips, strategy.risk_reward) == (30.0, 1.5)


@pytest.mark.parametrize("risk_reward", [0, -1])
def test_non_positive_risk_reward_is_rejected(risk_reward: float) -> None:
    with pytest.raises(ValueError, match="risk_reward"):
        SessionBreakout(risk_reward=risk_reward)


@pytest.mark.parametrize("max_range_pips", [0, -5])
def test_non_positive_max_range_is_rejected(max_range_pips: float) -> None:
    with pytest.raises(ValueError, match="max_range_pips"):
        SessionBreakout(max_range_pips=max_range_pips)


@pytest.mark.parametrize("name", ["Mars/Olympus", ""])
def test_unknown_session_timezone_is_rejected(name: str) -> None:
    with pytest.raises(ValueError, match="session_timezone"):
        SessionBreakout(session_timezone=name)


@pytest.mark.parametrize("name", ["UTC", "Europe/London", "broker", "Broker"])
def test_iana_names_and_the_broker_clock_are_accepted(name: str) -> None:
    SessionBreakout(session_timezone=name)
