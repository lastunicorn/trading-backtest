"""Concrete `TradingStrategy` implementations, versionless and freely editable.

`STRATEGIES` maps the name `backtest.py --strategy` accepts to the class it
builds (with its default parameters). Register a new strategy here to make it
runnable from the command line; it stays usable from code without that.
"""

from __future__ import annotations

from domain.pandas_approach.trading_strategy import TradingStrategy

__all__ = ["STRATEGIES"]

STRATEGIES: dict[str, type[TradingStrategy]] = {}
