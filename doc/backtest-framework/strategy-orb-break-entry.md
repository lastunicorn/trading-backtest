# ORB — Break Entry

`"strategy": {"name": "orb_break_entry"}` · class `strategies.orb_break_entry.OrbBreakEntry`

The New York Opening Range Break with a break entry, from [`doc/orb-break-entry.md`](../orb-break-entry.md). Stop orders at both edges of the 09:30–09:45 ET range open a trade the moment price breaks out.

For each New York date D:

1. The **opening range** is the high H and low L (wicks included) of the bars opening in [09:30, 09:45) ET. A day with no range bars, or with H == L, does not trade.
2. **Two stop orders** wait from 09:45 until 11:30 ET. The first bar opening in that window that reaches H opens a long at H. The first that reaches L opens a short at L. Each side fills at most once, and neither cancels the other, so a day has 0–2 trades. One bar through both levels opens both.
3. **Stop:** the range midpoint. **Target:** `risk_reward` × the risk (2R).
4. A trade still open at 16:00 ET (the NYSE close) is closed there (`manual-close`).

The doc doesn't say when an open trade ends. Step 4 is this implementation's choice; set `exit_at` to `null` to hold each trade until its stop or target instead.

The windows are compared against the bars as real instants, and positions are labelled on the data's own clock. So the strategy runs on broker-server (MT5) and UTC (Dukascopy) data alike, and 09:30 ET stays 09:30 ET across daylight-saving changes. The bar size must divide the 15-minute range (1m, 3m, 5m or 15m); anything else raises.

## Parameters

Each one can be set from a config's `strategy.parameters`. Times are `"HH:MM <zone>"`, with an IANA zone or `broker`.

| Parameter | Default | Meaning |
|---|---|---|
| `range_start`, `range_end` | `"09:30 America/New_York"`, `"09:45 America/New_York"` | the opening range (end exclusive); the orders start at `range_end` |
| `orders_expire` | `"11:30 America/New_York"` | no entry on a bar opening at or after it |
| `exit_at` | `"16:00 America/New_York"` | time stop (`exit_dt`); `null` for none |
| `risk_reward` | 2.0 | target distance ÷ stop distance |

The split days are the dates with a usable opening range, traded or not.

## Running it

The entry is at a level *inside* the trigger bar, so use the default `"resolve_from": "next-bar"`. It can't see a stop hit on the trigger bar itself, which makes it slightly optimistic. With the stop only half the range away, this matters more than for most strategies; `"entry-bar"` is the pessimistic bound for comparison. Fills are at the level even when a bar gaps through it (the framework's rule). Between 09:45 and 11:30 that should be rare.

`backtests/orb_break_entry/backtest.json` runs it on Dukascopy EURUSD M1 (UTC) with the bar's real spread (`"cost": {"spread": true}`) and `"splits": "dvt"`. The broker MT5 exports would work too, but those on the share carry no spread column. Three trades fall on Dukascopy days without ask prices (2021-11-12, 2022-03-11, 2023-11-17); they are charged 0 spread and listed in the report's Notes.

```bash
python3 backtest.py backtests/orb_break_entry
```

See also: [Running a backtest](running-a-backtest.md) · [framework overview](README.md)
