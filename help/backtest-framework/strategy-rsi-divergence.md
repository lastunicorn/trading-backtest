# RSI Divergence

`"strategy": "rsi_divergence"` · class `strategies.rsi_divergence.RsiDivergence`

Regular RSI divergences that leave the 30/70 band. It enters at the open of the bar after the pivot is confirmed, with the stop beyond the pivot's price extreme and the target at `risk_reward` × risk. Built on M15. Timezone-agnostic unless you give it an entry window.

## Parameters

Each one can be set from a config's `strategy_parameters`.

| Parameter | Default | Meaning |
|---|---|---|
| `rsi_length` | 14 | Wilder RSI period |
| `pivot_left`, `pivot_right` | 5, 5 | pivot lookback / confirmation bars |
| `range_lower`, `range_upper` | 5, 60 | allowed bar distance between the two pivots |
| `rsi_lower`, `rsi_upper` | 30, 70 | the band the divergence must start outside and end inside |
| `risk_reward` | 2.0 | target distance ÷ stop distance |
| `stop_buffer_pips` | 1.0 | stop distance beyond the pivot bar's low (long) / high (short) |
| `start_time`, `end_time` | `null`, `null` | optional entry window, each a time with its own timezone (see below) |

## Entry window

`start_time` and `end_time` limit entries to a time of day. A signal whose entry bar opens outside `[start_time, end_time)` is skipped. Only entries are limited. RSI and pivots still run over every bar, and a position opened inside the window runs to its stop or target as usual.

Each bound carries its own timezone, so `"08:00 Europe/London"` stays 08:00 London through daylight saving, whatever clock the data is on. The zone is `"broker"` or an IANA name. A time without a zone is rejected:

```json
"strategy_parameters": {"start_time": "08:00 Europe/London", "end_time": "12:00 Europe/London"}
```

- Either bound may be `null` (the default) or left out. With only `start_time`, the window runs to midnight in its zone. With only `end_time`, it runs from midnight.
- An `end_time` at or before `start_time` wraps past midnight (`"22:00 UTC"` → `"02:00 UTC"`).
- The two bounds may be in different zones.
- The window is compared with real instants, so `data.timezone` must be right for the source (`"America/New_York"` for histdata, `"UTC"` for Dukascopy, `"broker"` for this repo's MT5 exports).

`run.json` and the report record the bounds with their zone (`08:00:00 Europe/London`). The rule itself is `domain.time_window.TimeWindow`, which other strategies can reuse.

## Running it

Run with `"timeframe": "15m"` and `"resolve_from": "entry-bar"`. `backtests/rsi_divergence/backtest.json` does that on the raw M1 exports, and `backtests/rsi_divergence_dukascopy/` on Dukascopy data with spread costs:

```bash
python3 backtest.py backtests/rsi_divergence
```

See also: [Running a backtest](running-a-backtest.md) · [framework overview](README.md)
