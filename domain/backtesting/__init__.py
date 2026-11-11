"""How a backtest turns a strategy's entries into trades, results and
statistics: the `TradingStrategy` contract, `Position`s and their `Side`, cost
models, the exit rules (`Backtest`), trade results, splits and statistics.

Pure calculations over pandas DataFrames, on top of
`domain.market_data.historical_data.HistoricalData`; grouped as in
`doc/architecture/domain/backtesting.md`. This `__init__` imports nothing;
import from the modules directly (`from domain.backtesting.backtest import Backtest`).
"""
