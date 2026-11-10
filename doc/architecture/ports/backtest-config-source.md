# BacktestConfigSource

A [port](README.md) of the [application blueprint](../README.md).

*Python: `ports/backtest_config_access/`.* Reads the JSON file that drives one backtest and checks its **shape** only: known keys, JSON types, required keys. Whether the values make sense (a registered strategy, a known symbol) is the [LoadBacktestConfig use case](../use-cases/load-backtest-config.md)'s job. Its file format is [below](#file-format-backtest-config-file).

## Constants

`CONFIG_FILE_NAME = "backtest.json"`.

## Actions

| Action | Returns | Description |
|---|---|---|
| `find_config_file(path: Path)` | `Path` | `path` if it is a file; `path/backtest.json` if it is a folder. |
| `read_config(path: Path)` | `BacktestConfig` | See below. |

`read_config`:

1. Find the file; parse it as JSON; the top level must be an object.
2. Check the top-level keys, then `strategy`'s, `data_source`'s, `simulation`'s and `simulation.cost`'s: no unknown key, every value of its JSON type, every required key present ([key table](#keys)).
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

## File format: Backtest config file

One JSON file drives one backtest. It is passed directly, or as a folder holding `backtest.json`. User documentation: `doc/backtest-framework/backtest-config.md`.

```json
{
    "strategy": {
        "name": "narrow_asia_fade",
        "parameters": {"rel_vol_min": 1.8, "study_end": "13:00"}
    },
    "data_source": {
        "path": "../../data/eurusd/1min",
        "format": "metatrader",
        "symbol": "EURUSD",
        "timeframe": "1m",
        "timezone": "broker"
    },
    "simulation": {
        "timeframe": "5m",
        "ambiguity": "assume-sl",
        "cost": {"commission_pips": 1.7}
    },
    "out": "output",
    "splits": "dvt"
}
```

### Keys

| Key | JSON type | Required | Default | Meaning |
|---|---|---|---|---|
| `strategy` | object | yes | | which strategy runs, and with what |
| `strategy.name` | string | yes | | a [registry](../plugins/README.md#registry-and-parameters) name |
| `strategy.parameters` | object | no | `{}` | overrides of the strategy's parameters ([how values are written](../use-cases/load-backtest-config.md#parameter-conversion)) |
| `data_source` | object | yes | | the bars as they are on disk |
| `data_source.path` | string | yes | | a file or a folder; relative to the config file's folder |
| `data_source.format` | string | yes | | `metatrader`, `histdata` or `dukascopy` |
| `data_source.symbol` | string | yes | | a ticker in `SYMBOLS` |
| `data_source.timeframe` | string | no | `1m` | the source's bar size as stored |
| `data_source.timezone` | string | no | `UTC` | the clock of the source's timestamps: `broker`, `histdata` or an IANA name; never inferred from `format` |
| `simulation` | object | no | all defaults | the rules the positions are traded under |
| `simulation.timeframe` | string | no | `5m` | the bar size to backtest on; a whole multiple of `data_source.timeframe` |
| `simulation.ambiguity` | string | no | `exclude` | `exclude`, `assume-sl` or `assume-tp` |
| `simulation.cost` | object | no | **no cost** | |
| `simulation.cost.spread` | boolean | no | `false` | charge each trade the spread of the bar where it crosses to the ask |
| `simulation.cost.commission_pips` | number >= 0 | no | `0` | pips charged on every trade; without `spread`, the whole cost |
| `out` | string | yes | | the results folder, relative to the config file's folder; **overwritten** |
| `splits` | string | no | `none` | `none`, `dvt`, `monthly` or `yearly`; groups the statistics only |

- An unknown key, a value of the wrong JSON type and a missing required key are errors, never ignored or defaulted. A boolean is never a number.
- Where SL/TP checking starts is not a setting: each position's `entry_fill`, chosen by the strategy, decides it.
- Every check and its error: this port's [errors](#errors) (shape) and [LoadBacktestConfig](../use-cases/load-backtest-config.md) (values).
