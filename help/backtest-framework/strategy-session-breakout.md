# Session Breakout

`"strategy": "session_breakout"` · class `strategies.session_breakout.SessionBreakout`

The Tokyo/Asian session breakout from `tokyo-session-breakout.md`, ported from `session_breakout_strategy.py`. It matches that script trade for trade. `tests/strategies/session_breakout/test_script_parity.py` runs both on a synthetic M1 random walk on every `pytest` run, and the two also agree on all 912 trades of the canonical 2020–2026 M5 dataset.

For each UTC calendar day D:

1. The reference session sets H and L, wicks included. By default that is 09:00–18:00 Asia/Tokyo, which is 00:00–09:00 UTC. The day is cancelled if H − L exceeds `max_range_pips`.
2. From the session's end on D until its end on D+1, the first bar reaching H opens a long at H, and the first bar reaching L opens a short at L. Both can trigger on the same day.
3. The stop is the midpoint of [L, H]. The target is `risk_reward` × that risk.
4. A position still open at the session's end on D+1 is closed there (`manual-close`).

The session windows are converted to the data's clock, so the strategy runs on broker-server (MT5) and UTC (Dukascopy) data alike.

## Parameters

Each one can be set from a config's `strategy_parameters`.

| Parameter | Default | Meaning |
|---|---|---|
| `session_start`, `session_end` | 09:00, 18:00 | reference session, local time in `session_timezone` (end exclusive) |
| `session_timezone` | `"Asia/Tokyo"` | an IANA zone name, or `"broker"` for the broker-server clock |
| `max_range_pips` | 30.0 | a day whose session range is above this does not trade |
| `risk_reward` | 1.5 | target distance ÷ stop distance |

The defaults are the script's CLI defaults. The strategy description asks for a risk/reward of 1:2; set `"risk_reward": 2` for that.

## Kept from the script

These rules come from the code, not from `tokyo-session-breakout.md`, and they are kept for parity:

- **Breakouts are looked for until the session's end on D+1**, not until midnight as the description says.
- **A day's session only takes bars dated D in UTC, from 00:00 UTC.** A session crossing UTC midnight is cut there. A session that ends on D+1 never trades, because its breakout window is empty.
- **SL/TP are checked on the trigger bar itself**, so run it with `"resolve_from": "entry-bar"`. The trigger is at a level inside the bar, so for results rather than parity, `next-bar` is the stricter choice.
- **The script charges no costs** (`"cost_pips": 0`).

There is one departure: a day whose session has H == L is skipped. The script would open two zero-risk positions there, which a `Position` cannot hold. The same day is also left out of `split_days`. The split days are the days with a usable session, whatever their range, so tuning `max_range_pips` doesn't move the split boundaries.

The script records no price for a force-closed position and leaves those positions out of its "P/L %". The framework prices them at the close of the last bar before the time stop, so its totals include them.

## Running it

`backtests/session_breakout/backtest.json` runs with the parity settings (`entry-bar`, `exclude`, no costs) on the canonical broker-clock M5 dataset:

```bash
python3 backtest.py backtests/session_breakout
```

This prints 912 trades: 534 stop-loss hits, 321 take-profit hits, 32 manual closes and 25 ambiguous trades.

See also: [Running a backtest](running-a-backtest.md) · [framework overview](README.md)
