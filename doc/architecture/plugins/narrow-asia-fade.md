# `narrow_asia_fade`: NarrowAsiaFade

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/narrow_asia_fade.py`. Rules: `doc/strategies/narrow-asia-fade/`.* Candle DNA — Narrow Asia London Fade: when the Asia session's range is narrow, fade the first London break of it back inside.

## Parameters

| Name | Type | Default | Meaning |
|---|---|---|---|
| `asia_start` | `LocalTime` | 02:00 | Asia window start (broker clock) |
| `asia_end` | `LocalTime` | 10:00 | Asia window end, exclusive |
| `london_open` | `LocalTime` | 10:00 | first bar that can break the range |
| `study_end` | `LocalTime` | 14:00 | open time of the last bar traded (inclusive) |
| `narrow_threshold_pips` | `Float` | 21.72 | maximum Asia range; the discovery period's first quartile, then frozen |
| `rel_vol_min` | `Float` | 1.6 | minimum relative volume of the break bar |
| `rel_vol_length` | `Integer` | 20 | bars in the volume average |
| `stop_range_multiple` | `Float` | 1.0 | stop distance in Asia ranges |
| `max_missing_asia_bars` | `Integer` | 3 | Asia bars a day may miss |

No construction checks. The windows are minutes of the day, so they cannot wrap past midnight.

## Requirements on the data

| Requirement | Error |
|---|---|
| on the broker clock (`data.timezone == BROKER_SERVER_TZ`) | `WRONG_CLOCK`: `NarrowAsiaFade's windows are broker-server times; the data is on {timezone}` |
| minute bars (`timeframe.unit == Minute`) | `UNSUPPORTED_TIMEFRAME`: `NarrowAsiaFade needs intraday minute bars, got {timeframe}` |

## Steps

Work on the weekday bars only (Monday–Friday, by `datetime`), in order. Let `bar` be the bar length and minute-of-day = `hour × 60 + minute`.

1. **Relative volume**, for every weekday bar: `tick_volume` (or `volume` if there is no `tick_volume`) divided by its trailing mean over `rel_vol_length` bars (the bar itself included). `null` when there is no volume column, before the window is full, when any volume in the window is missing, or when the mean is not positive.
2. **Asia days.** For each date: its Asia bars are those with minute-of-day in `[asia_start, asia_end)`. `expected = max((asia_end − asia_start) in minutes ÷ bar minutes, rounded down, 1)`. Keep the day only if it has at least `expected − max_missing_asia_bars` Asia bars and their `H = max(high) > L = min(low)`.
3. For each Asia day:
   1. `range_pips = to_pips(H − L)`; skip the day if `range_pips > narrow_threshold_pips`.
   2. **Window:** that day's bars with minute-of-day in `[london_open, study_end]` (both ends included).
   3. **Break:** the first window bar with `high >= H` or `low <= L`. None: skip. Both on the same bar: skip (which side came first is unknowable).
   4. The break bar's relative volume must be `>= rel_vol_min` (a `null` fails).
   5. **Entry:** the first window bar **after** the break that trades back through the broken level: `low <= H` after an upside break, `high >= L` after a downside one. None: skip.
   6. `stop = range_pips × stop_range_multiple × pip_size`.

| Field | After an upside break | After a downside break |
|---|---|---|
| `side` | `SHORT` | `LONG` |
| `open_price` | `H` | `L` |
| `sl` | `H + stop` | `L − stop` |
| `tp` | `(H + L) / 2` | `(H + L) / 2` |
| `tag` | `fade-high` | `fade-low` |
| `open_dt` | the entry bar's `datetime` | |
| `entry_fill` | `AT_LEVEL` | |
| `exit_dt` | the day at `study_end`, plus one `bar` (the end of the last bar traded) | |

`split_days`: the Asia days of step 2, whatever their range.

Intended simulation: `simulation.timeframe` `5m`, `ambiguity` `assume-sl` (the strategy's design), `cost.commission_pips` 1.7.
