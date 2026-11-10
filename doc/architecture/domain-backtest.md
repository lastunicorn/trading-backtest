# Domain: Backtest

How a backtest turns a strategy's entries into trades, results and statistics. All of it is a pure calculation over `HistoricalData` ([domain-market-data.md](domain-market-data.md#8-historicaldata)): no files, no clock, no git. Recording a run and writing its files is the [RecordBacktest use case](use-cases/record-backtest.md)'s job. The strategy contract is in [plugins/](plugins/README.md#the-plugin-contract-tradingstrategy).

## Contents

1. [The pipeline](#1-the-pipeline)
2. [Position](#2-position)
3. [CostModel](#3-costmodel)
4. [Backtest and the exit rules](#4-backtest-and-the-exit-rules)
5. [Trade results](#5-trade-results)
6. [Splits](#6-splits)
7. [Statistics](#7-statistics)

---

## 1. The pipeline

```
HistoricalData ─► strategy.generate_positions ─► open Positions (entry, SL, TP, entry_fill, exit_dt?)
                                                   │
                       Backtest: close every position (the exit rules, the ONE place exits are decided)
                                                   │
       positions_to_frame ─► CostModel.cost_pips ─► trade_results ─► sort by open_dt
                                                   │
                       splits (optional) ─► statistics_by_split ─► BacktestResult(trades, statistics, notes)
```

- **Strategies decide entries only.** They return open positions; how each one closed is decided once, here.
- Each position is simulated **independently**: there is no portfolio, no position sizing, no limit on concurrent positions, and positions don't know about each other.
- **Costs come off before any statistic.**

---

## 2. Position

*Python: `domain/pandas_approach/position.py`, `side.py`.*

### Side (Enum)

`LONG` (`long`), `SHORT` (`short`).

### EntryFill (Enum)

Where in its entry bar a position filled, which decides whether that bar can hit its SL or TP.

| Value | Wire | Meaning | SL/TP checked from |
|---|---|---|---|
| `AT_LEVEL` | `at-level` | filled at a price inside the bar (a stop or limit order); OHLC can't tell whether the bar's extremes came before or after the fill | the **next** bar |
| `AT_OPEN` | `at-open` | filled at the bar's open (a market order after a closed signal bar); the whole bar came after the fill | the entry bar itself |

### PositionOutcome (Enum)

| Value | Wire | Meaning |
|---|---|---|
| `OPEN` | `open` | not closed yet |
| `STOP_LOSS_HIT` | `stop-loss-hit` | |
| `TAKE_PROFIT_HIT` | `take-profit-hit` | |
| `MANUAL_CLOSE` | `manual-close` | closed at its `exit_dt` (a time stop) |
| `END_OF_DATA` | `end-of-data` | still open when the bars ran out |
| `AMBIGUOUS` | `ambiguous` | one bar touched both SL and TP; it has no close price and no P&L |

The order of this list is the order of the `outcome_*` statistics.

### Position

One trade: opened by a strategy, closed by the backtest. Prices are raw price units; a position doesn't know its symbol's pip size.

| Property | Type | Set by | Notes |
|---|---|---|---|
| `open_dt` | `LocalDateTime` | strategy | the entry bar's open time |
| `open_price` | `Float` | strategy | |
| `side` | `Side` | strategy | |
| `sl` | `Float` | strategy | stop-loss level |
| `tp` | `Float` | strategy | take-profit level |
| `entry_fill` | `EntryFill = AT_LEVEL` | strategy | |
| `exit_dt` | `LocalDateTime?` | strategy | the moment it must be flat (a time stop); `null` for none |
| `tag` | `String = ""` | strategy | free text ("break-high"), a column to group on |
| `close_dt` | `LocalDateTime?` | backtest | |
| `close_price` | `Float?` | backtest | `null` only for `AMBIGUOUS` |
| `outcome` | `PositionOutcome = OPEN` | backtest | |

Invariants, checked on construction:

| Rule | Error |
|---|---|
| long: `sl < open_price < tp` | `INVALID_POSITION_LEVELS` (`long position needs sl < open_price < tp, got sl=…, open_price=…, tp=…`) |
| short: `tp < open_price < sl` | `INVALID_POSITION_LEVELS` |
| `exit_dt`, if set, is after `open_dt` | `EXIT_NOT_AFTER_OPEN` |

| Action | Returns | Description |
|---|---|---|
| `is_closed` | `Boolean` | `outcome != OPEN` |
| `close(at: LocalDateTime, price: Float?, outcome: PositionOutcome)` | `Void` | Records how it ended; the only way the close fields change. |

`close` errors:

| Code | Description |
|---|---|
| `POSITION_ALREADY_CLOSED` | A position closes once. |
| `CLOSE_WITH_OPEN_OUTCOME` | `outcome` is `OPEN`. |
| `CLOSE_BEFORE_OPEN` | `at < open_dt`. |
| `CLOSE_PRICE_MISMATCH` | `price` is `null` but the outcome isn't `AMBIGUOUS`, or the reverse. |

### `positions_to_frame(positions: List<Position>) -> Table<TradeRow>`

One row per position, in list order, with these columns in this order: `open_dt`, `side`, `open_price`, `sl`, `tp`, `entry_fill`, `exit_dt`, `close_dt`, `close_price`, `outcome`, `tag`. Enums become their wire values; missing timestamps and prices are `null`. An empty list gives an empty table with the same columns, so no caller special-cases "no trades".

---

## 3. CostModel

*Python: `domain/pandas_approach/cost_model.py`.* What each trade pays in friction, in pips.

### CostModel (abstract)

| Action | Returns | Description |
|---|---|---|
| `cost_pips(trades: Table<TradeRow>, data: HistoricalData)` | `List<Float>` | One round-trip cost per trade, aligned with the rows. |
| `notes(trades, data)` | `List<String>` | What a reader of the results should know about how the trades were charged. Empty by default. |

### FixedCost

| Property | Type | Notes |
|---|---|---|
| `pips` | `Float = 1.7` | >= 0 (`NEGATIVE_COST`); charged to every trade |

`1.7` is the domain's default, the friction the Narrow Asia Fade research assumed. A config **without** `simulation.cost` builds `FixedCost(pips = 0)`, not this default ([LoadBacktestConfig](use-cases/load-backtest-config.md)).

### SpreadCost

| Property | Type | Notes |
|---|---|---|
| `commission_pips` | `Float = 0` | >= 0 (`NEGATIVE_COST`); added to every trade |

Prices are bid. A long buys at the ask on entry and sells at the bid, so it pays the spread once, **at entry**; a short sells at the bid and buys back at the ask, so it pays it once, **at exit**. So:

- **Ask-side moment:** `open_dt` for a long, `close_dt` for a short.
- **Cost:** the `spread` (pips) of the bar containing that moment (`data.locate`), plus `commission_pips`. A bar whose spread is `null` (Dukascopy has whole days with no ask prices) is charged 0 spread.
- **Notes:** when any trade was charged 0 spread that way, one note: `{n} trade(s) charged 0 spread: their ask-side bar has no spread value (e.g. no ask price in the source). Opened {list}{more}.`, where `{list}` is the first 10 of those trades' `open_dt`, sorted, as `YYYY-MM-DD HH:MM`, joined by `, `, and `{more}` is ` and {k} more` when there are more than 10.

SL and TP are still triggered on bid prices: a short's stop the ask would have reached slightly earlier is not modelled.

| Code | Description |
|---|---|
| `NEGATIVE_COST` | `cost cannot be negative, got {x} pips` / `commission cannot be negative, got {x} pips`. |
| `SPREAD_REQUIRED` | `SpreadCost` on data without a `spread` column: `SpreadCost needs a 'spread' column in the historical data; use FixedCost instead`. |
| `NO_BAR_AT_ASK_MOMENT` | A trade's ask-side moment is before the first bar (or a short is still open). |

---

## 4. Backtest and the exit rules

*Python: `domain/pandas_approach/backtest.py`.*

### AmbiguityPolicy (Enum)

What to do when one bar touches both SL and TP: `EXCLUDE` (`exclude`, the default: record it `AMBIGUOUS`, no price, no P&L), `ASSUME_SL` (`assume-sl`: settle it as a stop), `ASSUME_TP` (`assume-tp`: settle it as a target).

### Backtest

| Property | Type | Notes |
|---|---|---|
| `strategy` | `TradingStrategy` | [plugins](plugins/README.md) |
| `data` | `HistoricalData` | |
| `cost_model` | `CostModel = FixedCost(1.7)` | |
| `ambiguity_policy` | `AmbiguityPolicy = EXCLUDE` | |
| `splits` | `SplitMode = NONE` | groups the statistics only ([Splits](#6-splits)) |

### `run() -> BacktestResult`

1. `positions = strategy.generate_positions(data)`.
2. Close every position under [the exit rules](#the-exit-rules).
3. `trades = positions_to_frame(positions)`.
4. `notes = cost_model.notes(trades, data)` (before the result columns are added).
5. `trades = trade_results(trades, data.symbol, cost_model.cost_pips(trades, data))`.
6. Stable-sort `trades` by `open_dt`.
7. If `splits` is not `NONE`: `by_date = split_labels(strategy.split_days(data), splits)`; add a `split` column, `assign_splits(trades.open_dt, by_date)`; the split names are `by_date`'s values in first-appearance order.
8. `statistics = statistics_by_split(trades, split names)`.

### The exit rules

Applied to each position on its own, using the bars' bid OHLC:

1. **Checks.** Every position must be open (`POSITION_NOT_OPEN`: `position opened at {open_dt} is already closed`) and its entry bar `e = data.locate(open_dt)` must exist (`POSITION_BEFORE_DATA`: `position opens at {open_dt}, before the first bar {start_dt}`). Neither is skipped: a silently dropped trade changes every statistic.
2. **First bar checked:** `first = e` for `AT_OPEN`, `e + 1` for `AT_LEVEL`.
3. **Last bar traded:** with no `exit_dt`, every bar to the end. With one, only bars **opening before** `exit_dt`: `stop` = index of the first bar with `datetime >= exit_dt`. If there is no such bar, the data ran out before the time stop.
4. **Hits.** Walk bars `first … stop − 1` and stop at the first bar where:
   - long: `high >= tp` (TP) or `low <= sl` (SL);
   - short: `low <= tp` (TP) or `high >= sl` (SL).

   The position closes at **that bar's open time** (OHLC doesn't say when inside the bar) and **at the level itself**, even when the bar gapped through it (so SL fills are optimistic after gaps). A bar hitting both is settled by `ambiguity_policy`: `AMBIGUOUS` with no price, or `STOP_LOSS_HIT` at `sl`, or `TAKE_PROFIT_HIT` at `tp`.
5. **No hit, time stop reached:** closes `MANUAL_CLOSE` at `close_dt = exit_dt`, price = close of the last bar traded (bar `stop − 1`, the price at `exit_dt`).
6. **No hit, data ran out** (no `exit_dt`, or no bar at or after it): closes `END_OF_DATA` at the last bar's open time and close price.

Example: a strategy that trades its 14:00 M5 bar and must be flat after it sets `exit_dt` to 14:05.

### BacktestResult

| Property | Type | Notes |
|---|---|---|
| `trades` | `Table<TradeResultRow>` | [Trade results](#5-trade-results) columns, plus `split` when splitting; sorted by `open_dt` |
| `statistics` | `Table<StatisticsRow>` | row `all`, then one per split, in order ([Statistics](#7-statistics)) |
| `notes` | `List<String>` | caveats from the cost model, for the report |

---

## 5. Trade results

*Python: `domain/pandas_approach/trade_results.py`.* `trade_results(trades, symbol, cost_pips) -> Table<TradeResultRow>` appends, in this order:

| Column | Type | Formula |
|---|---|---|
| `gross_pips` | `Float?` | `symbol.to_pips((close_price − open_price) × direction)`, direction +1 long, −1 short |
| `cost_pips` | `Float` | from the cost model |
| `net_pips` | `Float?` | `gross_pips − cost_pips`; **every statistic is computed from this** |
| `risk_pips` | `Float` | `symbol.to_pips(abs(open_price − sl))` |
| `net_r` | `Float?` | `net_pips / risk_pips` |
| `duration_min` | `Float` | minutes from `open_dt` to `close_dt` |

A trade without a close price (`AMBIGUOUS`) gets `null` `gross_pips`, `net_pips` and `net_r`: it stays in the table and the outcome counts but drops out of every P&L figure. `cost_pips` must be aligned with the trades (`COST_MISALIGNED` otherwise, a programming error).

---

## 6. Splits

*Python: `domain/pandas_approach/splits.py`.* How a backtest's trades are grouped for reporting. Splitting never changes a trade.

### SplitMode (Enum)

| Value | Wire | Groups |
|---|---|---|
| `NONE` | `none` | no grouping (default) |
| `DVT` | `dvt` | chronological discovery / validation / test, 60 / 20 / 20 of the days |
| `MONTHLY` | `monthly` | calendar month, labelled `YYYY-MM` |
| `YEARLY` | `yearly` | calendar year, labelled `YYYY` |

### Split (Enum)

`DISCOVERY` (`discovery`), `VALIDATION` (`validation`), `TEST` (`test`).

### Actions

| Action | Returns | Description |
|---|---|---|
| `split_dates(dates: List<Date>, discovery: Float = 0.6, validation: Float = 0.2)` | `Map<Date, Split>` | Sort the distinct dates; with `n` of them, the first `floor(n × discovery)` are discovery, up to `floor(n × (discovery + validation))` validation, the rest test. Never shuffled, so the same days always give the same boundaries. Requires `discovery > 0`, `validation > 0`, `discovery + validation < 1` (`INVALID_SPLIT_FRACTIONS`). |
| `split_labels(dates: List<Date>, mode: SplitMode)` | `Map<Date, String>` | Each distinct date → its split's name, in date order: the `Split` wire value for `DVT`, `YYYY-MM` for `MONTHLY`, `YYYY` for `YEARLY`. `NONE` has no labels (`NO_SPLIT_LABELS`). The map's values in first-appearance order are the split names in order. |
| `assign_splits(open_dts: List<LocalDateTime>, by_date: Map<Date, String>)` | `List<String>` | Each trade's split: the label of the date it **opens** on. A trade on a date the map doesn't cover is an error (`TRADE_DATE_NOT_IN_SPLIT`: `{n} trade date(s) not covered by the split, first {date}`): leaving it out would make the splits disagree with the totals. |

Which days are split is the strategy's choice (`split_days`): by default every day with a bar; a strategy that trades only some days splits over those, so the boundaries fall between tradable days.

---

## 7. Statistics

*Python: `domain/pandas_approach/statistics.py`.*

Rules:

- Every P&L figure is **net of costs**.
- A **win** is `net_pips > 0`, a **loss** `net_pips <= 0`. That is not the same as the outcome: a target closer than the cost is still a loss.
- Only **resolved** trades (with a `net_pips`) enter P&L figures. Ambiguous trades are counted in `trades` and `outcome_*` only.
- Drawdown and streaks follow the trades in `open_dt` order (stable).

### `compute_statistics(trades) -> Map<String, Float>`

The metrics, in this order (the order of the report and of `statistics.csv`'s columns):

| Metric | Type | Definition (`R` = resolved trades, `W` = wins, `L` = losses) |
|---|---|---|
| `trades` | `Integer` | all rows |
| `outcome_open` … `outcome_ambiguous` | `Integer` | count per `PositionOutcome`, in enum order: `outcome_open`, `outcome_stop-loss-hit`, `outcome_take-profit-hit`, `outcome_manual-close`, `outcome_end-of-data`, `outcome_ambiguous` |
| `excluded_ambiguous` | `Integer` | = `outcome_ambiguous` |
| `resolved` | `Integer` | `count(R)` |
| `wins` | `Integer` | `count(W)` |
| `losses` | `Integer` | `count(L)` |
| `win_rate_pct` | `Float` | `100 × wins / resolved`; NaN if `resolved = 0` |
| `total_gross_pips` | `Float` | sum of `gross_pips` over `R`; NaN if `R` empty |
| `total_cost_pips` | `Float` | sum of `cost_pips` over `R`; NaN if `R` empty |
| `total_net_pips` | `Float` | sum of `net_pips` over `R`; NaN if `R` empty |
| `total_net_r` | `Float` | sum of `net_r` over `R`; NaN if `R` empty |
| `avg_net_pips` | `Float` | mean of `net_pips` over `R` |
| `median_net_pips` | `Float` | median of `net_pips` over `R` (mean of the middle two for an even count) |
| `avg_win_pips` | `Float` | mean over `W` |
| `avg_loss_pips` | `Float` | mean over `L` (negative or zero) |
| `profit_factor` | `Float` | `gross_profit / gross_loss` where `gross_profit = sum(W)`, `gross_loss = −sum(L)`; if `gross_loss = 0`: `+∞` when `gross_profit > 0`, else NaN |
| `expectancy_r` | `Float` | mean of `net_r` over `R` |
| `max_drawdown_pips` | `Float` | [below](#max_drawdown) over `R`'s `net_pips`; NaN if `R` empty |
| `max_consecutive_losses` | `Integer` | longest run of consecutive `net_pips <= 0` in `R`; 0 if empty |
| `avg_duration_min` | `Float` | mean of `duration_min` over `R` |

A mean or median over no values is NaN. An empty table gives counts of 0 and NaN elsewhere.

#### `max_drawdown`

`equity = [0, cumulative sums of net_pips…]`; `peak = running maximum of equity`; the result is `max(peak − equity)`. NaN for no trades.

### `statistics_by_split(trades, splits: List<String> = []) -> Table<StatisticsRow>`

Row `all` (every trade), then one row per name in `splits`, in order, computed over the trades with that `split`. Every named split gets a row even when it has no trades, so a missing split shows as zeros instead of vanishing. With no splits, only `all`.
