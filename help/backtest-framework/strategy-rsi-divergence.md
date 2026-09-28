# RSI Divergence

`"strategy": "rsi_divergence"` · class `strategies.rsi_divergence.RsiDivergence`

Regular RSI divergences that leave the 30/70 band. It enters at the open of the bar after the pivot is confirmed, with the stop beyond the pivot's price extreme and the target at `risk_reward` × risk. Built on M15, timezone-agnostic.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| `rsi_length` | 14 | Wilder RSI period |
| `pivot_left`, `pivot_right` | 5, 5 | pivot lookback / confirmation bars |
| `range_lower`, `range_upper` | 5, 60 | allowed bar distance between the two pivots |
| `rsi_lower`, `rsi_upper` | 30, 70 | the band the divergence must start outside and end inside |
| `risk_reward` | 2.0 | target distance ÷ stop distance |
| `stop_buffer_pips` | 1.0 | stop distance beyond the pivot bar's low (long) / high (short) |

## Running it

Run with `"timeframe": "15m"` and `"resolve_from": "entry-bar"`. `backtests/rsi_divergence/backtest.json` does that on the raw M1 exports, and `backtests/rsi_divergence_dukascopy/` on Dukascopy data with spread costs:

```bash
python3 backtest.py backtests/rsi_divergence
```

See also: [Running a backtest](running-a-backtest.md) · [framework overview](README.md)
