# ScanRsiDivergences

A [use case](README.md) of the [application blueprint](../README.md).

Detects RSI divergences on M5 bars resampled from MetaTrader M1 exports: the plain indicator, so its divergences are **not** the `rsi_divergence` plugin's entries (no 30/70 band filter, M5 rather than M15).

## Input

| Field | Type | Default |
|---|---|---|
| `source` | `Path` | a folder of MetaTrader M1 exports or one file |
| `rsi_length` | `Integer` | 14 |
| `pivot_left` | `Integer` | 5 |
| `pivot_right` | `Integer` | 5 |
| `range_lower` | `Integer` | 5 |
| `range_upper` | `Integer` | 60 |
| `include_hidden` | `Boolean` | `false` |
| `progress` | callback? | |

## Output

| Field | Type | Notes |
|---|---|---|
| `bars` | `Table<BarRow>` | the M5 bars scanned |
| `divergences` | `List<Divergence>` | sorted by `end_time` |

## Steps

1. `bars = BuildCleanDataset(source, timeframe = 5m, progress)` (MetaTrader reader).
2. `oscillator = rsi(bars.close, rsi_length)`.
3. `divergences = find_divergences(bars, oscillator, pivot_left, pivot_right, range_lower, range_upper, include_hidden)` ([domain/indicators.md](../domain/indicators.md#2-divergence)).

In the Python code these steps are inline in the CLI's `main()`; a rewrite should give them their own function, as above.

## Errors

`NO_USABLE_SOURCE_FILES` from BuildCleanDataset.
