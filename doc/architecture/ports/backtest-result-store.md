# BacktestResultStore

A [port](README.md) of the [application blueprint](../README.md).

*Python: `backtest.py`'s `write_results`.* In the Python code this lives in the entry script rather than under `ports/`; a rewrite should put it behind a port like the others.

## Actions

| Action | Returns | Description |
|---|---|---|
| `write_results(result: BacktestResult, run_info: RunInfo, report: String, out_dir: Path, price_decimals: Integer)` | `List<Path>` | Creates `out_dir` if needed and writes, **overwriting**, `positions.csv`, `statistics.txt`, `statistics.csv` and `run.json`, returned in that order. Prices in `positions.csv` are rounded to `price_decimals` (the symbol's), pips to 2 places, `net_r` to 3, `duration_min` to 1. Formats: [external-formats.md](../external-formats.md#5-backtest-result-files). |

## Errors

| Code | Description |
|---|---|
| `OUTPUT_WRITE_FAILED` | Any failure to create the folder or write a file. |

## DTOs

`BacktestResult` is a domain type ([domain-backtest.md](../domain-backtest.md#backtestresult)).

### RunInfo

The provenance of one backtest run, built by [RecordBacktest](../use-cases.md#4-recordbacktest) and written as `run.json`. A JSON object, keys in this order:

| Key | Type | Content |
|---|---|---|
| `created` | `String` | `now()`, ISO 8601 to the second (`2026-11-09T13:21:25`) |
| `strategy.name` | `String` | the config's `strategy.name`, or the strategy's own `name` when none was given |
| `strategy.class` | `String` | the strategy's fully qualified class name (`strategies.narrow_asia_fade.NarrowAsiaFade`) |
| `strategy.parameters` | `Map<String, Any>` | every parameter, in the spelling a config reads back ([recording parameters](../plugins.md#recording-parameters)) |
| `data.symbol` | `String` | ticker |
| `data.timeframe` | `String` | `SampleSize` text |
| `data.timezone` | `String` | the clock's **display name** (`broker-server (America/New_York+7h)`, `UTC`) |
| `data.first_bar`, `data.last_bar` | `String` | ISO 8601 (`2020-01-02T00:00:00`) |
| `data.bars` | `Integer` | |
| `simulation.cost_model` | `Map` | `class` (`FixedCost` / `SpreadCost`) followed by its properties (`pips` / `commission_pips`) |
| `simulation.ambiguity_policy` | `String` | wire value |
| `splits` | `String` | wire value |
| `trades` | `Integer` | number of trades |
| `git` | `Map` | `commit`, `dirty` from [`GitCommit`](run-environment.md#gitcommit) |
| `source` | `String` | only when given: `{data_source.path} ({format})` from the CLI |
| `notes` | `List<String>` | only when there are any: `BacktestResult.notes` |
