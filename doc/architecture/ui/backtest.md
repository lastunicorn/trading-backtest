# `backtest`

A [CLI](README.md) of the [application blueprint](../README.md).

*Python: `backtest.py`.* Runs a backtest from a JSON config and writes its results. Use case: [RunBacktestFromConfig](../use-cases/run-backtest-from-config.md).

```
backtest <config>
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `config` | `Path` | required | a JSON config file, or a folder holding `backtest.json` |

## Validation

| Input | Rule | On failure |
|---|---|---|
| `config` | given | exit 2 |
| the config's contents | every rule of [LoadBacktestConfig](../use-cases/load-backtest-config.md) | `ERROR: {file}: …`, exit 1 |

There is no other UI-level validation: every setting lives in the config, whose format is on the [BacktestConfigSource page](../ports/backtest-config-source.md#file-format-backtest-config-file).

Errors caught (exit 1): every `ValueError` and `FileNotFoundError` class error, from loading the config, loading the data or running the strategy (wrong clock, missing spread column, missing files), and `NO_USABLE_SOURCE_FILES` (no source file yielded any bar). Any other error, a strategy's bug included, ends with a stack trace.

## Output

1. The data loader's progress lines.
2. A blank line, then the report: the full content of `statistics.txt` ([format](../ports/backtest-result-store.md#statisticstxt)).
3. `Wrote {path}` for each of the four files.
4. A blank line, then `Execution time: {seconds, 2 decimals}s`.
