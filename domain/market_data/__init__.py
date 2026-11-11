"""The concepts behind the bars themselves: timeframes (`sample_size`),
instruments (`symbol`), clocks (`broker_clock`), daily time windows
(`time_window`), trading sessions (`trading_session`,
`trading_session_instance`), the bar frame's operations (`frames`,
`shift_timezone`, `session_ohlc`) and `HistoricalData`, the validated bars a
backtest runs on.

Grouped as in `doc/architecture/domain/market-data.md`. Most modules are
stdlib only; `frames`, `shift_timezone`, `session_ohlc` and `historical_data`
need pandas. This `__init__` imports nothing, so a stdlib port importing one
module gains no pandas dependency; import from the modules directly
(`from domain.market_data.sample_size import SampleSize`).
"""
