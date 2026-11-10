# OpeningRangeStrategy (shared base)

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/opening_range.py`.* Not registered: the base of the two Opening Range Break strategies. It finds, for each date, a session's opening range, the window in which orders may fill, and the time stop.

## Parameters (inherited by both ORB strategies)

| Name | Type | Default | Constraint | Meaning |
|---|---|---|---|---|
| `session` | `TradingSession` | `New York` | | the range starts at its start |
| `opening_range_minutes` | `Integer` | 15 | > 0 | the range's length; orders start at its end |
| `order_expiry_minutes` | `Integer` | 120 | > 0 | from the session's start: no entry on a bar opening at or after it |
| `exit_at_session_end` | `Boolean` | `true` | | flat by the session's end; `false`: no time stop |
| `risk_reward` | `Float` | per strategy | > 0 | target distance ÷ stop distance |

## Windows on a date `D`

Let `start` be `D` at `session.start_time`, in its zone.

| Bound | Value |
|---|---|
| range start | `start` |
| range end | `start` + `opening_range_minutes` of wall-clock time |
| orders expire | `start` + `order_expiry_minutes` of wall-clock time |
| session end | `session.create_session(D).end_dt` |

They must satisfy `range end <= orders expire < session end`. This is checked on construction (on the reference date 2026-01-05) and again on every traded date, since two zones may disagree only on some dates: `SESSION_WINDOWS_OUT_OF_ORDER`, with the message `the range ({n} minutes) must end by the orders' expiry ({m} minutes) after the {session} start on {date}` or `order_expiry_minutes {m} must expire the orders before the {session} end on {date}`.

## Requirements on the data

Minute bars whose length divides the opening range (measured on the reference date), so no bar straddles its end: `UNSUPPORTED_TIMEFRAME`, `{name} needs minute bars dividing its {n}-minute opening range, got {timeframe}`. Any clock: bars are compared with the windows as instants, and positions are emitted on the data's own clock.

## Opening ranges

For each distinct date `D` of the bars' wall-clock time in the session's start zone, in order:

1. Range bars: those whose instant is in `[range start, range end)`. None: skip the date.
2. `H = max(high)`, `L = min(low)` over them; skip unless `H > L`. `M = (H + L) / 2`.
3. **Order window:** the bars whose instant is in `[range end, orders expire)`.
4. `exit_dt`: the session end converted to the data's clock (no zone), when `exit_at_session_end`; otherwise `null`.

`split_days` (both ORB strategies): the dates with a usable range, traded or not.
