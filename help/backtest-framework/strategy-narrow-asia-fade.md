# Narrow Asia London Fade

`"strategy": "narrow_asia_fade"` · class `strategies.narrow_asia_fade.NarrowAsiaFade`

"Candle DNA — Narrow Asia London Fade": on a day with a narrow Asia range, wait for London to break it, then fade the break back toward the Asia midpoint. It needs broker-server-clock minute bars (M5 as researched) and raises on anything else.

## Parameters

Each one can be set from a config's `strategy_parameters`.

| Parameter | Default | Meaning |
|---|---|---|
| `asia_start`, `asia_end` | 02:00, 10:00 | Asia window (end exclusive), broker-server time |
| `london_open` | 10:00 | breaks are looked for from here… |
| `study_end` | 14:00 | …up to and including the bar opening here; also the time stop (`exit_dt` = end of that bar) |
| `narrow_threshold_pips` | 21.72 | maximum Asia range (discovery Q1, frozen) |
| `rel_vol_min`, `rel_vol_length` | 1.6, 20 | break-bar tick volume over its 20-bar SMA must reach 1.6 |
| `stop_range_multiple` | 1.0 | stop distance = this × the Asia range |
| `max_missing_asia_bars` | 3 | tolerated gaps in the Asia window |

## Running it

The strategy was designed with `"ambiguity": "assume-sl"` and `"resolve_from": "next-bar"`. `backtests/narrow_asia_fade/backtest.json` runs it that way:

```bash
python3 backtest.py backtests/narrow_asia_fade
```

See also: [Running a backtest](running-a-backtest.md) · [framework overview](README.md)
