# `rsi_divergence`: RsiDivergence

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/rsi_divergence.py`. Rules: `doc/strategies/rsi-divergence/`.* A reversal on regular RSI divergences that leave overbought/oversold territory.

## Parameters

| Name | Type | Default | Constraint | Meaning |
|---|---|---|---|---|
| `rsi_length` | `Integer` | 14 | | RSI period |
| `pivot_left` | `Integer` | 5 | | bars a pivot must beat on its left |
| `pivot_right` | `Integer` | 5 | | bars on its right; also the confirmation delay |
| `range_lower` | `Integer` | 5 | | minimum bars between two pivots |
| `range_upper` | `Integer` | 60 | | maximum bars between two pivots |
| `rsi_lower` | `Float` | 30 | | oversold bound |
| `rsi_upper` | `Float` | 70 | | overbought bound |
| `risk_reward` | `Float` | 2.0 | > 0 | |
| `stop_buffer_pips` | `Float` | 1.0 | >= 0 | stop distance beyond the pivot's extreme |
| `start_time` | `ZonedTime?` | `null` | must carry a zone | first entry time of day, inclusive |
| `end_time` | `ZonedTime?` | `null` | must carry a zone | last entry time of day, exclusive |

## Steps

1. `osc = rsi(close, rsi_length)`; `divergences = find_divergences(data, osc, pivot_left, pivot_right, range_lower, range_upper, include_hidden = false)`; `filter_regular_by_band(divergences, rsi_lower, rsi_upper)` ([domain-indicators.md](../domain-indicators.md)).
2. `signals = open_positions(data, divergences, pivot_right, rsi_lower, rsi_upper)`: the entry is the open of the bar `pivot_right + 1` bars after the newer pivot; long below `rsi_lower`, short above `rsi_upper`.
3. For each signal, with `pivot` = the newer pivot's bar and `entry` = the signal's `open_price`:
   1. Skip it unless its `open_time`, read on the data's clock, is inside `TimeWindow(start_time, end_time)` ([domain-market-data.md](../domain-market-data.md#4-timewindow)). Only entries are limited: RSI and pivots run over every bar.
   2. Long: `sl = pivot.low − stop_buffer_pips × pip_size`; skip unless `sl < entry`; `tp = entry + risk_reward × (entry − sl)`.
   3. Short: `sl = pivot.high + stop_buffer_pips × pip_size`; skip unless `sl > entry`; `tp = entry − risk_reward × (sl − entry)`.

   (The skip happens when price has already run past the pivot's extreme by the entry bar's open.)

| Field | Value |
|---|---|
| `side` | the signal's |
| `open_dt`, `open_price` | the entry bar's `datetime` and `open` |
| `sl`, `tp` | as above |
| `entry_fill` | `AT_OPEN` (the entry bar is checked for SL/TP too) |
| `exit_dt` | `null`: managed to its stop or target, or the data's end |
| `tag` | `bullish divergence, pivot YYYY-MM-DD HH:MM` (long) / `bearish divergence, pivot …` (short), the newer pivot's time |

`split_days`: the default (every date with a bar).

Clock-agnostic without an entry window (RSI and pivots depend on bar order only); with one, `data.timezone` must be right.

Intended simulation: `simulation.timeframe` `15m`, the timeframe its entries were designed on.
