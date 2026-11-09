# ORB — Retest Entry

`"strategy": {"name": "orb_retest_entry"}` · class `strategies.orb_retest_entry.OrbRetestEntry`

The Opening Range Break with a retest entry, from [its rules](orb-retest-entry-rules.md). Once price breaks out of a session's opening range, a limit order at the range's midpoint waits for it to come back, and the trade opens there in the direction of the break. The session is a parameter: by default New York's (`NEW_YORK_SESSION`, 09:30–16:00 ET, the NYSE bells), so the range is 09:30–09:45 ET as the rules describe.

For each date D in the session's time zone (the zone of its start):

1. The **opening range** is the high H and low L (wicks included) of the bars opening in the first `opening_range_minutes` (15) from the session's start, so [09:30, 09:45) ET by default. M is its midpoint. A day with no range bars, or with H == L, does not trade.
2. The **break** is the first bar opening between the range's end and `order_expiry_minutes` (120) after the session's start (09:45–11:30 ET by default) that reaches H (an upside break) or L (a downside one). If that bar reaches both, the day does not trade.
3. The break places a **limit order at M**: a long after an upside break, a short after a downside one. It waits from the bar after the break until the same expiry, 11:30 ET. The first bar that reaches M fills it at M. A day has at most one trade.
4. **Stop:** the other side of the range (L for the long, H for the short), half the range away. **Target:** `risk_reward` × the risk beyond M (3R).
5. A trade still open at the session's end (16:00 ET by default, the NYSE close) is closed there (`manual-close`).

Where the rules leave room, this implementation decides:

- **A touch is a break.** A bar reaching H or L breaks it, as in [ORB — Break Entry](../orb-break-entry/orb-break-entry-implementation.md); it doesn't have to close beyond it.
- **The break must also come before the expiry.** A later break would place an order that is already cancelled.
- **The fill is the entry.** Nothing has to confirm the move after the retest: the rules' "then continues in the initial direction" is what the trade hopes for, not an entry condition.
- **The break bar can't fill the order.** OHLC can't say whether it reached M before or after the break, so fills start on the next bar.
- **A first break through both sides skips the day.** Which side broke first is unknowable from one bar.
- **A break the other way can't come first.** Any bar reaching the far side of the range passes M, so it fills the order (and may stop it out in the same bar, see below).
- **Step 5's time stop isn't in the rules.** Set `exit_at_session_end` to `false` to hold each trade until its stop or target instead.

The windows are compared against the bars as real instants, and positions are labelled on the data's own clock. So the strategy runs on broker-server (MT5) and UTC (Dukascopy) data alike, and each session follows its own zone's daylight saving. The bar size must be in minutes and divide `opening_range_minutes` (for the default 15: 1m, 3m, 5m or 15m); anything else raises.

## Parameters

Each one can be set from a config's `strategy.parameters`. They are `OrbBreakEntry`'s, with a 3R default: both strategies share the range and its windows (`strategies.opening_range.OpeningRangeStrategy`).

| Parameter | Default | Meaning |
|---|---|---|
| `session` | `"New York"` | the session whose start opens the range and whose end is the time stop: a name in `domain.trading_session.SESSIONS` (`"Tokyo"`, `"Asia"`, `"London"`, `"New York"`). From Python, any `TradingSession` |
| `opening_range_minutes` | 15 | the opening range's length in minutes (end exclusive, wall clock); the break can come from its end |
| `order_expiry_minutes` | 120 | minutes from the session's start (wall clock) after which neither a break nor a fill counts; not before the range's end, and before the session's end |
| `exit_at_session_end` | `true` | time stop (`exit_dt`) at the session's end; `false` for none |
| `risk_reward` | 3.0 | target distance ÷ stop distance |

The rules suggest adapting the range's length and the target per symbol. They are meant for American indexes such as the Nasdaq 100, for which the repo has neither a `Symbol` nor data yet. For an index whose cash session isn't in `SESSIONS`, see the [break entry's note](../orb-break-entry/orb-break-entry-implementation.md#parameters) (the DAX's Xetra session is `"London"`).

The split days are the dates with a usable opening range, traded or not.

## Running it

The fill is at a level *inside* its bar, so the positions are `entry_fill` `at-level` and SL/TP are checked from the next bar. For a limit order that is optimistic. Price reaches M before it can reach the stop beyond it, so a fill bar that also reached the stop was certainly stopped out, but the simulator doesn't see it and the trade lives on to a later outcome. On DEUIDXEUR M1 (London session, 2020-01 to 2026-08), 5 of 982 fill bars touched the stop, and all 5 hit it again on a later bar, so the results didn't change. Check again on coarser bars or a more volatile symbol.

Fills are at M even when a bar gaps through it, where a real limit order would fill at the better open: slightly pessimistic.

`backtests/orb_retest_entry/backtest.json` runs it on Dukascopy DEUIDXEUR M1 (UTC) at the London open with the bar's real spread (`"cost": {"spread": true}`) and `"splits": "dvt"`. Eleven trades fall on Dukascopy days without ask prices; they are charged 0 spread and listed in the report's Notes.

```bash
python3 backtest.py backtests/orb_retest_entry
```

See also: [Running a backtest](../../backtest-framework/running-a-backtest.md) · [framework overview](../../backtest-framework/README.md) · [all strategies](../README.md)
