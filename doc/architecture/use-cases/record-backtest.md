# RecordBacktest

A [use case](README.md) of the [application blueprint](../README.md).

Runs a prepared `Backtest` and records it: the domain result, its provenance (clock, git), the human report and the four result files. The reusable entry point for anything that builds its own `Backtest` (a notebook, a parameter sweep).

## Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `backtest` | `Backtest` | | strategy, data, cost model, ambiguity policy, split mode |
| `out_dir` | `Path` | | overwritten |
| `source` | `String?` | `null` | recorded as `run.json`'s `source` |
| `strategy_name` | `String?` | `null` | recorded as `strategy.name`; the strategy's own `name` (its class name) when absent |
| `now` | RunEnvironment `now` | the real clock | in Python, a parameter of `build_run_info` only |
| `git_commit` | RunEnvironment `git_commit` | the real repository | in Python, a parameter of `build_run_info` only |

## Output: `BacktestRun`

| Field | Type | Notes |
|---|---|---|
| `result` | `BacktestResult` | as `Backtest.run()` returned it |
| `run_info` | `RunInfo` | [DTO](../ports/backtest-result-store.md#runinfo) |
| `report` | `String` | the content of `statistics.txt` |
| `paths` | `List<Path>` | the four files written |

## Steps

1. `result = backtest.run()` ([domain/backtest.md](../domain/backtest.md#4-backtest-and-the-exit-rules)).
2. `run_info = build_run_info(backtest, result, source, strategy_name, now, git_commit)`: the [RunInfo](../ports/backtest-result-store.md#runinfo) fields, from the backtest's strategy, data, cost model and settings, `now()` and `git_commit()`.
3. `report = format_report(result, run_info)`: the text laid out in [BacktestResultStore](../ports/backtest-result-store.md#statisticstxt).
4. `paths = BacktestResultStore.write_results(result, run_info, report, out_dir, price_decimals = data.symbol.price_decimals)`.

## Errors

| Code | Description |
|---|---|
| strategy errors | Raised by `generate_positions`, e.g. `WRONG_CLOCK`, `UNSUPPORTED_TIMEFRAME` ([plugins](../plugins/README.md)), or `INVALID_POSITION_LEVELS` from a faulty strategy. |
| `POSITION_NOT_OPEN`, `POSITION_BEFORE_DATA` | A strategy returned a closed position, or one before the first bar. |
| `SPREAD_REQUIRED`, `NO_BAR_AT_ASK_MOMENT` | From `SpreadCost`. |
| `TRADE_DATE_NOT_IN_SPLIT` | A trade on a day the strategy's `split_days` doesn't include. |
| `OUTPUT_WRITE_FAILED` | From BacktestResultStore. |
