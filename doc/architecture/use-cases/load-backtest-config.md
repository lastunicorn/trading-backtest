# LoadBacktestConfig

A [use case](README.md) of the [application blueprint](../README.md).

Reads a backtest config and checks that its values fit what a backtest can run, so a typo fails before any data is loaded instead of silently falling back to a default.

## Input

| Field | Type | Notes |
|---|---|---|
| `config_path` | `Path` | a JSON file, or a folder holding `backtest.json` |

## Output

`BacktestConfig` ([DTO](../ports/backtest-config-source.md#backtestconfig)), with `strategy.parameters` converted to the strategy's field types.

## Steps

1. `file = BacktestConfigSource.find_config_file(config_path)`; `config = BacktestConfigSource.read_config(file)` (the shape checks).
2. `strategy.name` is a key of `STRATEGIES`.
3. `splits` is a `SplitMode` wire value.
4. `data_source.format` is a `SourceFormat` wire value; `data_source.symbol` is in `SYMBOLS` (`by_ticker`); `data_source.timezone` resolves (`timezone_by_name`).
5. `simulation.ambiguity` is an `AmbiguityPolicy` wire value; `simulation.timeframe` and `data_source.timeframe` parse as `SampleSize`; `simulation.timeframe.can_be_resampled_from(data_source.timeframe)`.
6. `strategy.parameters`: every name must be one of the strategy's parameters; convert each value by the parameter's type ([table below](#parameter-conversion)); then construct the strategy once with them, so its own validation runs now (the instance is discarded).
7. Return the config with the converted parameters.

The checks run in this order, and the first failure is returned.

## Parameter conversion

| Parameter type | JSON value accepted | Becomes |
|---|---|---|
| `T?` (optional) | `null`, or what `T` accepts | `null`, or as `T` |
| `Integer` | a whole number (not `true`/`false`, not `5.0`) | `Integer` |
| `Float` | any number (not `true`/`false`) | `Float` |
| `Boolean` | `true` / `false` | `Boolean` |
| `String` | a string | `String` |
| `LocalTime` | `"HH:MM"` (seconds allowed; ISO 8601, no UTC offset) | a time on the data's clock |
| `ZonedTime` | `"HH:MM <zone>"`: exactly a time and a clock name (`timezone_by_name`) separated by whitespace, e.g. `"08:00 Europe/London"`, `"10:00 broker"` | a time in that zone |
| `TradingSession` | a `SESSIONS` name (`"London"`) | that session |
| anything else | none | `CONFIG_PARAMETER_UNSETTABLE` |

## Helper: `cost_model(cost: CostConfig) -> CostModel`

`SpreadCost(commission_pips)` when `cost.spread`, else `FixedCost(pips = commission_pips)`. A config without `simulation.cost` therefore costs **nothing**, not the domain's 1.7-pip default.

## Errors

Every message is prefixed with the config file's path, `{file}: `.

| Code | Description |
|---|---|
| `CONFIG_*` of BacktestConfigSource | Not found, invalid JSON, unknown key, wrong type, missing key, negative commission ([BacktestConfigSource](../ports/backtest-config-source.md)). |
| `CONFIG_INVALID_CHOICE` | `strategy.name`, `splits`, `data_source.format`, `simulation.ambiguity` or a session parameter not among its choices: `"{key}" is "{value}"; choose one of {choices}`. |
| `CONFIG_UNKNOWN_SYMBOL` | `"data_source.symbol": unknown symbol ticker '{ticker}'`. |
| `CONFIG_UNKNOWN_TIMEZONE` | `"data_source.timezone" is "{value}": not "broker", "histdata" or an IANA time zone name such as "UTC" or "America/New_York"`. |
| `CONFIG_INVALID_TIMEFRAME` | `"{key}": {the INVALID_INTERVAL message}`. |
| `CONFIG_TIMEFRAME_NOT_MULTIPLE` | `"simulation.timeframe" {tf} is not a whole multiple of the source's "data_source.timeframe" {source tf}; resampling only coarsens`. |
| `CONFIG_UNKNOWN_PARAMETER` | `"strategy.parameters": {strategy} has no parameter(s) {names}; its parameters: {names, or none}`. |
| `CONFIG_PARAMETER_WRONG_TYPE` | `"strategy.parameters.{key}" must be {a whole number \| a number \| true or false \| a string}, got {value as JSON}`. |
| `CONFIG_PARAMETER_BAD_TIME` | `"strategy.parameters.{key}" must be a time {form}, got {value as JSON}`, where `{form}` is `"HH:MM"` for a `LocalTime` and `"HH:MM <zone>" (e.g. "08:00 Europe/London" or "10:00 broker")` for a `ZonedTime`. |
| `CONFIG_PARAMETER_UNSETTABLE` | `"strategy.parameters.{key}" has type {type}, which a JSON config cannot set`. |
| `CONFIG_PARAMETERS_REJECTED` | The strategy refused the values: `invalid "strategy.parameters" for {strategy}: {the strategy's message}`. |
