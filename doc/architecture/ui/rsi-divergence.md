# `rsi_divergence`

A [CLI](README.md) of the [application blueprint](../README.md).

*Python: `rsi_divergence.py`.* Prints the RSI divergences found on M5 bars resampled from MetaTrader M1 exports. Use case: [ScanRsiDivergences](../use-cases/scan-rsi-divergences.md).

```
rsi_divergence <source> [--rsi-length N] [--pivot-left N] [--pivot-right N] [--range-lower N] [--range-upper N] [--hidden]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | required | a folder of M1 exports, or one file |
| `--rsi-length` | `Integer` | 14 | |
| `--pivot-left` | `Integer` | 5 | |
| `--pivot-right` | `Integer` | 5 | also the confirmation delay |
| `--range-lower` | `Integer` | 5 | minimum bars between two pivots |
| `--range-upper` | `Integer` | 60 | maximum bars between two pivots |
| `--hidden` | flag | off | report hidden divergences too |

## Validation

Only the argument parser's: `source` given, the numbers whole (exit 2). Ranges are not checked (a rewrite should require positive values and `range_lower <= range_upper`). No error is caught: `NO_USABLE_SOURCE_FILES` ends with a stack trace.

## Output

```
==========================================================================================   (90 '=')
EURUSD RSI DIVERGENCE SCAN
==========================================================================================
Source: {source}
{progress lines}

{n} M5 bars, {first datetime} -> {last datetime}

{k} divergence(s) found:
------------------------------------------------------------------------------------------   (90 '-')
{category, left in 8} {direction, left in 8} {start_time} -> {end_time}
...

Execution time: {s}s
```

The heading says EURUSD whatever the data is.
