# RunBacktestFromConfig

A [use case](README.md) of the [application blueprint](../README.md).

The whole backtest run the `backtest` CLI performs: config → data → strategy → recorded results.

## Input

| Field | Type | Notes |
|---|---|---|
| `config_path` | `Path` | a JSON file, or a folder holding `backtest.json` |
| `progress` | callback? | |

## Output

`BacktestRun` (as RecordBacktest).

## Steps

1. `config = LoadBacktestConfig(config_path)`.
2. `timeframe = SampleSize.Parse(config.simulation.timeframe)`; `symbol = by_ticker(config.data_source.symbol)`.
3. `data = LoadHistoricalData(config.data_source.path, SourceFormat(config.data_source.format), timeframe, symbol, timezone_by_name(config.data_source.timezone), progress)`.
4. `strategy = STRATEGIES[config.strategy.name](config.strategy.parameters)`; the parameters not given keep the strategy's defaults.
5. `backtest = Backtest(strategy, data, cost_model(config.simulation.cost), AmbiguityPolicy(config.simulation.ambiguity), SplitMode(config.splits))`.
6. Return `RecordBacktest(backtest, config.out, source = "{data_source.path} ({format})", strategy_name = config.strategy.name)`.

## Errors

Those of LoadBacktestConfig, LoadHistoricalData and RecordBacktest.
