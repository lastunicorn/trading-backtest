# Domain

The concepts behind the market data and the trades taken on it, and every calculation on them. Pure: nothing in the domain reads or writes a file, the clock or git, and it depends on no other part of the application. Types and rules are in [conventions.md](../conventions.md).

| Page | Covers |
|---|---|
| [market-data.md](market-data.md) | `SampleSize`, `Symbol`, clocks, `TimeWindow`, `TradingSession`, `Bar`, bar table operations, `HistoricalData` |
| [backtesting.md](backtesting.md) | `Position`, cost models, the backtest and its exit rules, trade results, splits, statistics |
| [indicators.md](indicators.md) | RSI and divergence detection |
