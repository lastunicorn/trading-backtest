# Plugins: Strategies

A strategy is a plugin: it decides where to **enter** and returns open positions; the backtest decides how each one closed ([domain-backtest.md](domain-backtest.md#4-backtest-and-the-exit-rules)). Strategies are found by name in a registry, built from a config's parameters and recorded in `run.json`. Adding one touches nothing outside the plugins (plus its tests and documentation page). Types and rules are in [conventions.md](conventions.md).

The trading rules of each strategy are also written for traders in `doc/strategies/<name>/<name>-implementation.md`; this page is the contract a re-implementation must meet.

## Contents

1. [The plugin contract: TradingStrategy](#1-the-plugin-contract-tradingstrategy)
2. [Registry and parameters](#2-registry-and-parameters)
3. [`narrow_asia_fade`: NarrowAsiaFade](#3-narrow_asia_fade-narrowasiafade)
4. [OpeningRangeStrategy (shared base)](#4-openingrangestrategy-shared-base)
5. [`orb_break_entry`: OrbBreakEntry](#5-orb_break_entry-orbbreakentry)
6. [`orb_retest_entry`: OrbRetestEntry](#6-orb_retest_entry-orbretestentry)
7. [`rsi_divergence`: RsiDivergence](#7-rsi_divergence-rsidivergence)
8. [`session_breakout`: SessionBreakout](#8-session_breakout-sessionbreakout)

---

## 1. The plugin contract: TradingStrategy

*Python: `domain/pandas_approach/trading_strategy.py`.* An abstract base every strategy implements. A strategy is an **immutable value**: its parameters are fixed at construction, and two runs with the same parameters on the same data return the same positions.

| Action | Returns | Description |
|---|---|---|
| `name` | `String` | A label for reports; the class name unless overridden. |
| `parameters()` | `Map<String, Any>` | The settings that define this run: every parameter, in declaration order, with its value (a `TradingSession` stays an object). |
| `split_days(data: HistoricalData)` | `List<Date>` | The days the discovery / validation / test split is cut over. Default: every date with a bar, in order. Override when the strategy trades only some days, so the boundaries fall between tradable days. |
| `generate_positions(data: HistoricalData)` | `List<Position>` | **Abstract.** Every entry the strategy takes over `data`, as open positions ([Position](domain-backtest.md#2-position)): `open_dt`, `open_price`, `side`, `sl`, `tp`, `entry_fill`, optionally `exit_dt` and `tag`. |

Obligations of `generate_positions`:

- **No look-ahead.** It sees the whole history, so a signal decided on bar `i` may use bars up to `i` only. This is the strategy's responsibility; the framework cannot check it.
- **Open positions only**, each opening at or after the first bar (the backtest refuses anything else).
- **Choose `entry_fill` honestly:** `AT_LEVEL` for an order filled at a level inside its bar, `AT_OPEN` for an entry at a bar's open.
- **Set `exit_dt`** to the moment the position must be flat, when the strategy has a time stop.
- **Fail loudly** on data it can't trade correctly (wrong clock, wrong bar size) instead of trading the wrong hours.

Construction validates the parameters; an invalid one is the error `INVALID_PARAMETER` with a message naming it. The order of positions in the list doesn't matter: the backtest sorts trades by `open_dt` (stable).

---

## 2. Registry and parameters

### The registry, `STRATEGIES: Map<String, StrategyConstructor>`

*Python: `strategies/__init__.py`.* Maps the name a config's `strategy.name` accepts to the strategy it builds. A strategy outside the registry still works from code, just not from a config.

| Name | Strategy | Section |
|---|---|---|
| `narrow_asia_fade` | NarrowAsiaFade | [§3](#3-narrow_asia_fade-narrowasiafade) |
| `orb_break_entry` | OrbBreakEntry | [§5](#5-orb_break_entry-orbbreakentry) |
| `orb_retest_entry` | OrbRetestEntry | [§6](#6-orb_retest_entry-orbretestentry) |
| `rsi_divergence` | RsiDivergence | [§7](#7-rsi_divergence-rsidivergence) |
| `session_breakout` | SessionBreakout | [§8](#8-session_breakout-sessionbreakout) |

### Parameters

A strategy's parameters are its constructor arguments, each with a type and a default. A config's `strategy.parameters` overrides any subset; the rest keep their defaults. The types a config can set are `Integer`, `Float`, `Boolean`, `String`, `LocalTime`, `ZonedTime`, `TradingSession` and optional versions of these; how each is written in JSON is in [use-cases.md](use-cases.md#parameter-conversion). A parameter of any other type can only be set from code.

`LocalTime` and `ZonedTime` are different types on purpose: a `LocalTime` is read on the data's own clock (`"10:00"`), a `ZonedTime` names its zone (`"10:00 broker"`, `"08:00 Europe/London"`), so neither can be written as the other.

### Recording parameters

`run.json` and the report record `parameters()` in the spelling a config reads back where there is one:

| Value | Recorded as |
|---|---|
| `ZonedTime` | `"HH:MM:SS {clock name}"` (`"08:00:00 Europe/London"`, `"10:00:00 broker"`) |
| `LocalTime` | `"HH:MM:SS"` |
| a standard `TradingSession` | its `SESSIONS` name (`"London"`) |
| another `TradingSession` | `{"start_time": …, "end_time": …, "name": …}`, its bounds recorded as `ZonedTime`s |
| `null`, numbers, booleans, strings | as JSON |

---

## 3. `narrow_asia_fade`: NarrowAsiaFade

*Python: `strategies/narrow_asia_fade.py`. Rules: `doc/strategies/narrow-asia-fade/`.* Candle DNA — Narrow Asia London Fade: when the Asia session's range is narrow, fade the first London break of it back inside.

### Parameters

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

### Requirements on the data

| Requirement | Error |
|---|---|
| on the broker clock (`data.timezone == BROKER_SERVER_TZ`) | `WRONG_CLOCK`: `NarrowAsiaFade's windows are broker-server times; the data is on {timezone}` |
| minute bars (`timeframe.unit == Minute`) | `UNSUPPORTED_TIMEFRAME`: `NarrowAsiaFade needs intraday minute bars, got {timeframe}` |

### Steps

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

---

## 4. OpeningRangeStrategy (shared base)

*Python: `strategies/opening_range.py`.* Not registered: the base of the two Opening Range Break strategies. It finds, for each date, a session's opening range, the window in which orders may fill, and the time stop.

### Parameters (inherited by both ORB strategies)

| Name | Type | Default | Constraint | Meaning |
|---|---|---|---|---|
| `session` | `TradingSession` | `New York` | | the range starts at its start |
| `opening_range_minutes` | `Integer` | 15 | > 0 | the range's length; orders start at its end |
| `order_expiry_minutes` | `Integer` | 120 | > 0 | from the session's start: no entry on a bar opening at or after it |
| `exit_at_session_end` | `Boolean` | `true` | | flat by the session's end; `false`: no time stop |
| `risk_reward` | `Float` | per strategy | > 0 | target distance ÷ stop distance |

### Windows on a date `D`

Let `start` be `D` at `session.start_time`, in its zone.

| Bound | Value |
|---|---|
| range start | `start` |
| range end | `start` + `opening_range_minutes` of wall-clock time |
| orders expire | `start` + `order_expiry_minutes` of wall-clock time |
| session end | `session.create_session(D).end_dt` |

They must satisfy `range end <= orders expire < session end`. This is checked on construction (on the reference date 2026-01-05) and again on every traded date, since two zones may disagree only on some dates: `SESSION_WINDOWS_OUT_OF_ORDER`, with the message `the range ({n} minutes) must end by the orders' expiry ({m} minutes) after the {session} start on {date}` or `order_expiry_minutes {m} must expire the orders before the {session} end on {date}`.

### Requirements on the data

Minute bars whose length divides the opening range (measured on the reference date), so no bar straddles its end: `UNSUPPORTED_TIMEFRAME`, `{name} needs minute bars dividing its {n}-minute opening range, got {timeframe}`. Any clock: bars are compared with the windows as instants, and positions are emitted on the data's own clock.

### Opening ranges

For each distinct date `D` of the bars' wall-clock time in the session's start zone, in order:

1. Range bars: those whose instant is in `[range start, range end)`. None: skip the date.
2. `H = max(high)`, `L = min(low)` over them; skip unless `H > L`. `M = (H + L) / 2`.
3. **Order window:** the bars whose instant is in `[range end, orders expire)`.
4. `exit_dt`: the session end converted to the data's clock (no zone), when `exit_at_session_end`; otherwise `null`.

`split_days` (both ORB strategies): the dates with a usable range, traded or not.

---

## 5. `orb_break_entry`: OrbBreakEntry

*Python: `strategies/orb_break_entry.py`. Rules: `doc/strategies/orb-break-entry/`.* Stop orders at both sides of the opening range.

Parameters: those of [OpeningRangeStrategy](#4-openingrangestrategy-shared-base), with `risk_reward` = **2.0**.

### Steps

For each opening range (`H`, `L`, `M`, order window, `exit_dt`), two independent stop orders; each fills at most once and they don't cancel each other, so a date has 0–2 trades (one bar through both levels opens both):

| Field | Long order | Short order |
|---|---|---|
| fills on | the first window bar with `high >= H` | the first window bar with `low <= L` |
| `side` | `LONG` | `SHORT` |
| `open_price` | `H` | `L` |
| `sl` | `M` | `M` |
| `tp` | `H + risk_reward × abs(H − M)` | `L − risk_reward × abs(L − M)` |
| `tag` | `break-high` | `break-low` |
| `open_dt` | the fill bar's `datetime` | |
| `entry_fill` | `AT_LEVEL` (SL/TP checked from the next bar: it can't see a stop hit on the fill bar, a slight optimism) | |
| `exit_dt` | the range's `exit_dt` | |

Fills are at the level even when a bar gaps through it.

---

## 6. `orb_retest_entry`: OrbRetestEntry

*Python: `strategies/orb_retest_entry.py`. Rules: `doc/strategies/orb-retest-entry/`.* After the first break of the opening range, a limit order at its midpoint.

Parameters: those of [OpeningRangeStrategy](#4-openingrangestrategy-shared-base), with `risk_reward` = **3.0**.

### Steps

For each opening range (`H`, `L`, `M`, order window, `exit_dt`):

1. **Break:** the first window bar with `high >= H` (upside) or `low <= L` (downside). None: skip. Both on one bar: skip.
2. **Fill:** from the bar **after** the break to the window's end, the first bar reaching `M`: `low <= M` after an upside break, `high >= M` after a downside one. None: skip. So a date has 0–1 trades. (The break bar can't fill: OHLC can't say whether it reached `M` before or after the break.)

| Field | After an upside break | After a downside break |
|---|---|---|
| `side` | `LONG` | `SHORT` |
| `open_price` | `M` | `M` |
| `sl` | `L` | `H` |
| `tp` | `M + risk_reward × abs(M − L)` | `M − risk_reward × abs(M − H)` |
| `tag` | `retest-high` | `retest-low` |
| `open_dt` | the fill bar's `datetime` | |
| `entry_fill` | `AT_LEVEL` | |
| `exit_dt` | the range's `exit_dt` | |

`AT_LEVEL` makes it optimistic: price reaches `M` before the stop beyond it, so a fill bar that also reached the stop was stopped out, but the simulator doesn't check the fill bar.

---

## 7. `rsi_divergence`: RsiDivergence

*Python: `strategies/rsi_divergence.py`. Rules: `doc/strategies/rsi-divergence/`.* A reversal on regular RSI divergences that leave overbought/oversold territory.

### Parameters

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

### Steps

1. `osc = rsi(close, rsi_length)`; `divergences = find_divergences(data, osc, pivot_left, pivot_right, range_lower, range_upper, include_hidden = false)`; `filter_regular_by_band(divergences, rsi_lower, rsi_upper)` ([domain-indicators.md](domain-indicators.md)).
2. `signals = open_positions(data, divergences, pivot_right, rsi_lower, rsi_upper)`: the entry is the open of the bar `pivot_right + 1` bars after the newer pivot; long below `rsi_lower`, short above `rsi_upper`.
3. For each signal, with `pivot` = the newer pivot's bar and `entry` = the signal's `open_price`:
   1. Skip it unless its `open_time`, read on the data's clock, is inside `TimeWindow(start_time, end_time)` ([domain-market-data.md](domain-market-data.md#4-timewindow)). Only entries are limited: RSI and pivots run over every bar.
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

---

## 8. `session_breakout`: SessionBreakout

*Python: `strategies/session_breakout.py`. Rules: `doc/strategies/session-breakout/`.* Breakout of a reference session's range (Tokyo by default). It reproduces a removed standalone script trade for trade, **including the script's quirks**, which are part of the contract (a parity test checks the trades against the script's recorded output, `tests/strategies/session_breakout/_script_trades.py`).

### Parameters

| Name | Type | Default | Constraint | Meaning |
|---|---|---|---|---|
| `session_start` | `LocalTime` | 09:00 | | reference session start, in `session_timezone` |
| `session_end` | `LocalTime` | 18:00 | | reference session end, in `session_timezone` |
| `session_timezone` | `String` | `Asia/Tokyo` | a clock name (`timezone_by_name`) | `UNKNOWN_SESSION_TIMEZONE`: `unknown session_timezone '{name}'` |
| `max_range_pips` | `Float` | 30.0 | > 0 | a wider session cancels the day |
| `risk_reward` | `Float` | 1.5 | > 0 | |
| `check_trigger_bar` | `Boolean` | `false` | | the script's rule: SL/TP may hit on the trigger bar (`AT_OPEN`); for parity, not for results |

The reference session is `TradingSession(session_start, session_end)`, both read in `session_timezone`.

### Steps

Convert every bar's `datetime` to its instant (UTC). For each distinct **UTC date** `D` of the bars, in order:

1. `s = session.create_session(D)`; `midnight = D 00:00 UTC`, `next_midnight = midnight + 1 day`.
2. Session bars: instants in `[max(s.start, midnight), min(s.end, next_midnight))`. None: skip. `H = max(high)`, `L = min(low)`; skip unless `H > L`.
3. `exit = session.end_time_utc_on(D + 1)`. **Breakout window:** instants in `[max(s.end, midnight), exit)`.
4. Skip the day if `to_pips(H − L) > max_range_pips`.
5. `M = (H + L) / 2`. Two independent orders, as in OrbBreakEntry:

| Field | Long | Short |
|---|---|---|
| fills on | the first window bar with `high >= H` | the first window bar with `low <= L` |
| `side` | `LONG` | `SHORT` |
| `open_price` | `H` | `L` |
| `sl` | `M` | `M` |
| `tp` | `H + risk_reward × abs(H − M)` | `L − risk_reward × abs(L − M)` |
| `tag` | `break-high` | `break-low` |
| `entry_fill` | `AT_OPEN` if `check_trigger_bar`, else `AT_LEVEL` | |
| `exit_dt` | `exit` converted to the data's clock (no zone) | |

`split_days`: the days of step 2, **not** filtered by `max_range_pips`, so tuning it doesn't move the split boundaries.

The script's quirks, kept on purpose:

- Breakouts are looked for until the session's end on `D + 1`, not until midnight as the written rules say.
- A day's session bars are only those on UTC date `D`: a session crossing UTC midnight is cut there, and one ending on `D + 1` never trades (its breakout window is empty).
- The session starts no earlier than 00:00 UTC on `D`.

One departure from the script: a day whose session has `H == L` is skipped (the script opened two zero-risk positions, which a `Position` can't represent).

Parity simulation: `check_trigger_bar` `true`, `simulation.ambiguity` `exclude`, `cost.commission_pips` 0.
