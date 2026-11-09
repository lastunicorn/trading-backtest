"""Tests for `strategies.orb_break_entry.OrbBreakEntry.__init__`: its defaults.

Checking the parameters is `OpeningRangeStrategy.__post_init__`'s, tested in
`tests/strategies/opening_range/`.
"""

from domain.trading_session import NEW_YORK_SESSION
from strategies.orb_break_entry import OrbBreakEntry


def test_defaults_match_the_description() -> None:
    strategy = OrbBreakEntry()

    assert strategy.session == NEW_YORK_SESSION    # 09:30-16:00 ET
    assert (strategy.opening_range_minutes, strategy.order_expiry_minutes) == (15, 120)
    assert strategy.exit_at_session_end is True
    assert strategy.risk_reward == 2.0
