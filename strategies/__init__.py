"""Concrete `TradingStrategy` implementations, versionless and freely editable.

`STRATEGIES` maps the name a `backtest.py` config's `strategy.name` accepts to the class it
builds (with its default parameters). Register a new strategy here to make it
runnable from the command line; it stays usable from code without that.
"""

from __future__ import annotations

from domain.backtesting.trading_strategy import TradingStrategy
from strategies.narrow_asia_fade import NarrowAsiaFade
from strategies.orb_break_entry import OrbBreakEntry
from strategies.orb_retest_entry import OrbRetestEntry
from strategies.rsi_divergence import RsiDivergence
from strategies.session_breakout import SessionBreakout

__all__ = ["STRATEGIES"]

STRATEGIES: dict[str, type[TradingStrategy]] = {
    "narrow_asia_fade": NarrowAsiaFade,
    "orb_break_entry": OrbBreakEntry,
    "orb_retest_entry": OrbRetestEntry,
    "rsi_divergence": RsiDivergence,
    "session_breakout": SessionBreakout,
}
