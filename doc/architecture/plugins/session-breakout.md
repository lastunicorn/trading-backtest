# `session_breakout`: SessionBreakout

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/session_breakout.py`. Rules: `doc/strategies/session-breakout/`.* Breakout of a reference session's range (Tokyo by default). It reproduces a removed standalone script trade for trade, **including the script's quirks**, which are part of the contract (a parity test checks the trades against the script's recorded output, `tests/strategies/session_breakout/_script_trades.py`).

## Parameters

| Name | Type | Default | Constraint | Meaning |
|---|---|---|---|---|
| `session_start` | `LocalTime` | 09:00 | | reference session start, in `session_timezone` |
| `session_end` | `LocalTime` | 18:00 | | reference session end, in `session_timezone` |
| `session_timezone` | `String` | `Asia/Tokyo` | a clock name (`timezone_by_name`) | `UNKNOWN_SESSION_TIMEZONE`: `unknown session_timezone '{name}'` |
| `max_range_pips` | `Float` | 30.0 | > 0 | a wider session cancels the day |
| `risk_reward` | `Float` | 1.5 | > 0 | |
| `check_trigger_bar` | `Boolean` | `false` | | the script's rule: SL/TP may hit on the trigger bar (`AT_OPEN`); for parity, not for results |

The reference session is `TradingSession(session_start, session_end)`, both read in `session_timezone`.

## Steps

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
