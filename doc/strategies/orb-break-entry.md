# ORB — Break Entry

`"strategy": {"name": "orb_break_entry"}` · class `strategies.orb_break_entry.OrbBreakEntry`

The Opening Range Break with a break entry, from [its rules](orb-break-entry-rules.md). Stop orders at both edges of a session's opening range open a trade the moment price breaks out. The session is a parameter: by default New York's (`NEW_YORK_SESSION`, 09:30–16:00 ET, the NYSE bells), so the range is 09:30–09:45 ET as the doc describes.

For each date D in the session's time zone (the zone of its start):

1. The **opening range** is the high H and low L (wicks included) of the bars opening in the first `opening_range_minutes` (15) from the session's start, so [09:30, 09:45) ET by default. A day with no range bars, or with H == L, does not trade.
2. **Two stop orders** wait from the range's end until `order_expiry_minutes` (120) after the session's start: 09:45–11:30 ET by default. The first bar opening in that window that reaches H opens a long at H. The first that reaches L opens a short at L. Each side fills at most once, and neither cancels the other, so a day has 0–2 trades. One bar through both levels opens both.
3. **Stop:** the range midpoint. **Target:** `risk_reward` × the risk (2R).
4. A trade still open at the session's end (16:00 ET by default, the NYSE close) is closed there (`manual-close`).

The doc doesn't say when an open trade ends. Step 4 is this implementation's choice; set `exit_at_session_end` to `false` to hold each trade until its stop or target instead.

The windows are compared against the bars as real instants, and positions are labelled on the data's own clock. So the strategy runs on broker-server (MT5) and UTC (Dukascopy) data alike, and each session follows its own zone's daylight saving: 08:00 London stays 08:00 London in the weeks when the UK and US switch on different dates. The bar size must be in minutes and divide `opening_range_minutes` (for the default 15: 1m, 3m, 5m or 15m); anything else raises.

## Parameters

Each one can be set from a config's `strategy.parameters`.

| Parameter | Default | Meaning |
|---|---|---|
| `session` | `"New York"` | the session whose start opens the range and whose end is the time stop: a name in `domain.trading_session.SESSIONS` (`"Tokyo"`, `"Asia"`, `"London"`, `"New York"`). From Python, any `TradingSession` |
| `opening_range_minutes` | 15 | the opening range's length in minutes (end exclusive, wall clock); the orders start at its end |
| `order_expiry_minutes` | 120 | minutes from the session's start (wall clock) after which no entry is taken; not before the range's end, and before the session's end |
| `exit_at_session_end` | `true` | time stop (`exit_dt`) at the session's end; `false` for none |
| `risk_reward` | 2.0 | target distance ÷ stop distance |

`order_expiry_minutes` counts from the session's start, not from the range's end, so a longer range shortens the order window rather than moving its expiry. `run.json` records a standard session by its name, and any other one by its bounds.

For an index whose cash session isn't in `SESSIONS`, check whether one of them is the same instant. The DAX's Xetra session (09:00–17:30 Frankfurt) is `"London"` (08:00–16:30 London): the UK and Germany change their clocks on the same dates.

The split days are the dates with a usable opening range, traded or not.

## Running it

The entry is at a level *inside* the trigger bar, so its positions are `entry_fill` `at-level` and SL/TP are checked from the next bar. It can't see a stop hit on the trigger bar itself, which makes it slightly optimistic. With the stop only half the range away, this matters more than for most strategies. Fills are at the level even when a bar gaps through it (the framework's rule). Between 09:45 and 11:30 that should be rare.

`backtests/orb_break_entry/backtest.json` runs it on Dukascopy EURUSD M1 (UTC) with the bar's real spread (`"cost": {"spread": true}`) and `"splits": "dvt"`. The broker MT5 exports would work too, but those on the share carry no spread column. Three trades fall on Dukascopy days without ask prices (2021-11-12, 2022-03-11, 2023-11-17); they are charged 0 spread and listed in the report's Notes.

```bash
python3 backtest.py backtests/orb_break_entry
```

See also: [Running a backtest](../backtest-framework/running-a-backtest.md) · [framework overview](../backtest-framework/README.md) · [all strategies](README.md)
