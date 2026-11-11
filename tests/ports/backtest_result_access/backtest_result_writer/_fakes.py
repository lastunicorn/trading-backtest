"""Shared builders for the `ports.backtest_result_access.backtest_result_writer` tests."""

from datetime import datetime

from domain.backtesting.backtest import Backtest, BacktestResult
from ports.backtest_result_access import RunProvenance
from ports.run_environment import GitCommit
from tests.domain.backtesting.backtest._fakes import ScriptedStrategy, data

PROVENANCE = RunProvenance(created=datetime(2026, 3, 4, 5, 6, 7), git=GitCommit("abc1234", dirty=False))


def result(entry_days=(0,), results=None, *, days=10, **settings) -> BacktestResult:
    """`ScriptedStrategy(entry_days)` run over `data(days, results)`; `settings` are the other `Backtest` fields."""
    return Backtest(ScriptedStrategy(list(entry_days)), data(days, results or {}), **settings).run()
