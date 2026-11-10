# `calculate_daily_sessions`

A [CLI](README.md) of the [application blueprint](../README.md).

*Python: `calculate_daily_sessions.py`.* Prints the open, high, low and close of trading sessions for every day of a source. Use case: [CollectDailySessions](../use-cases/collect-daily-sessions.md).

```
calculate_daily_sessions [source] [--source-format F] [--session NAME]... [--source-timezone TZ] [--source-symbol TICKER]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | a machine-specific folder (`/nfs/YubabaFinance/trading/historical data/arty/eurusd/1min`) | optional; a rewrite should make it required |
| `--source-format` | `SourceFormat` | `metatrader` | |
| `--session` | a `SESSIONS` name | `Asia` | repeat for several; reported in the order given |
| `--source-timezone` | clock name | `broker` | the files' clock; `UTC` for Dukascopy |
| `--source-symbol` | ticker | `EURUSD` | sets the price decimals |

## Validation

| Input | Rule | On failure |
|---|---|---|
| `--source-format`, `--session` | among the choices | exit 2 |
| `--source-timezone` | `timezone_by_name` resolves it | `ERROR: unknown --source-timezone '{name}'`, exit 1 (checked after parsing, unlike `read_csv`'s exit 2; a rewrite should make them consistent) |
| `--source-symbol` | in `SYMBOLS` | `ERROR: unknown symbol ticker '{ticker}'`, exit 1 |

Errors caught (exit 1): the use case's `ValueError`, `FileNotFoundError` and `RuntimeError` class errors (wrong clock for the format, no source files, nothing readable).

## Output

`Reading {source} ({format}, {clock name} clock)`, the loader's progress lines and a blank line. Then for each session:

```
=== {name} session ({window}, end exclusive) ===
date           open     high      low    close   bars
2020-01-02  1.12112  1.12210  1.12001  1.12150    108
...
  {n} session-days
```

followed by a blank line; or, with no bar in the window, `  (no bars in window)` and a blank line.

- `{window}`: `09:00-18:00 Asia/Tokyo`, or `{start} {zone} - {end} {zone}` when the bounds are in different zones (clock names as `timezone_name` gives them).
- `date` is left-aligned in 10 characters; prices are right-aligned, `price_decimals` places, in the width of the widest formatted high; `bars` right-aligned in 5; columns separated by two spaces.
