# BacktestConfigSource

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/backtest_config_access/`.* Reads the JSON file that drives one backtest and checks its **shape** only: known keys, JSON types, required keys. Whether the values make sense (a registered strategy, a known symbol) is the [LoadBacktestConfig use case](../use-cases.md#3-loadbacktestconfig)'s job. The file format is in [external-formats.md](../external-formats.md#4-backtest-config-file).

## Constants

`CONFIG_FILE_NAME = "backtest.json"`.

## Actions

| Action | Returns | Description |
|---|---|---|
| `find_config_file(path: Path)` | `Path` | `path` if it is a file; `path/backtest.json` if it is a folder. |
| `read_config(path: Path)` | `BacktestConfig` | See below. |

`read_config`:

1. Find the file; parse it as JSON; the top level must be an object.
2. Check the top-level keys, then `strategy`'s, `data_source`'s, `simulation`'s and `simulation.cost`'s: no unknown key, every value of its JSON type, every required key present ([key table](../external-formats.md#keys)).
3. JSON type rules: a JSON boolean is never a number; a whole number is accepted where a number is expected and converted to `Float`.
4. `simulation.cost.commission_pips` must not be negative.
5. Resolve `data_source.path` and `out` against **the config file's folder**, not the working directory, folding `..` away (symbolic links untouched). An absolute path stays as is.
6. `strategy.parameters` is kept as raw JSON values.

## Errors

Every message is prefixed with the config file's path, `{file}: `.

| Code | Description |
|---|---|
| `CONFIG_NOT_FOUND` | `no backtest config at {path}` (a missing file, or a folder without `backtest.json`). |
| `CONFIG_INVALID_JSON` | `not valid JSON: {parser message}`. |
| `CONFIG_NOT_AN_OBJECT` | `expected a JSON object, got {type}`. |
| `CONFIG_UNKNOWN_KEY` | `unknown key(s) {keys}; allowed: {keys}` (nested keys spelled `data_source.path`). |
| `CONFIG_WRONG_TYPE` | `"{key}" must be {a string \| a number \| a whole number \| true or false \| a list \| a JSON object}, got {value as JSON}`. |
| `CONFIG_MISSING_KEY` | `"{key}" is required`. |
| `CONFIG_NEGATIVE_COMMISSION` | `"simulation.cost.commission_pips" cannot be negative, got {value}`. |

## DTOs

### BacktestConfig

The config file, shape-checked (`read_config`), or value-checked too (`load_backtest_config`, which also types `strategy.parameters`). Field names are the JSON keys.

| Property | Type | Default |
|---|---|---|
| `strategy` | `StrategyConfig` | required |
| `data_source` | `DataSourceConfig` | required |
| `out` | `Path` | required; resolved against the config's folder |
| `simulation` | `SimulationConfig` | all defaults |
| `splits` | `String` (a `SplitMode` wire value) | `none` |

### StrategyConfig

| Property | Type | Default |
|---|---|---|
| `name` | `String` (a key of `STRATEGIES`) | required |
| `parameters` | `Map<String, Any>` | `{}`; raw JSON values from `read_config`, the strategy's field types after `load_backtest_config` |

### DataSourceConfig

| Property | Type | Default |
|---|---|---|
| `path` | `Path` | required; a file or a folder; resolved against the config's folder |
| `format` | `String` (a `SourceFormat` wire value) | required |
| `symbol` | `String` (a ticker) | required |
| `timeframe` | `String` (a `SampleSize`) | `1m`; the source's bar size as stored |
| `timezone` | `String` (a clock name) | `UTC`; the clock of the source's timestamps |

### SimulationConfig

| Property | Type | Default |
|---|---|---|
| `timeframe` | `String` (a `SampleSize`) | `5m`; the bar size to backtest on |
| `ambiguity` | `String` (an `AmbiguityPolicy` wire value) | `exclude` |
| `cost` | `CostConfig` | all defaults: no cost |

### CostConfig

| Property | Type | Default |
|---|---|---|
| `spread` | `Boolean` | `false`; charge each trade the spread of its ask-side bar |
| `commission_pips` | `Float` | `0`; charged on every trade; without `spread`, the whole cost |
