# Domain: Market Data

Part of the [domain](README.md) of the [application blueprint](../README.md).

The concepts behind the bars themselves: timeframes, instruments, clocks, daily time windows, trading sessions, the bar table's operations and `HistoricalData`, the validated bars a backtest runs on. Pure calculations: nothing here reads or writes a file, the clock or git. Types and rules are in [conventions.md](../conventions.md).

## Contents

1. [SampleSize](#1-samplesize)
2. [Symbol](#2-symbol)
3. [Clocks (time zones)](#3-clocks-time-zones)
4. [TimeWindow](#4-timewindow)
5. [TradingSession](#5-tradingsession)
6. [Bar and BarBlock](#6-bar-and-barblock)
7. [Bar table operations](#7-bar-table-operations)
8. [HistoricalData](#8-historicaldata)
9. [Legacy, not needed for a rewrite](#9-legacy-not-needed-for-a-rewrite)

---

## 1. SampleSize

*Python: `domain/market_data/sample_size.py`.* A bar width: an amount and a unit, written compactly as `"5m"`, `"4h"`, `"7d"`, `"2w"`, `"3M"`. Used for every timeframe in configs, CLIs and `HistoricalData`.

### SampleUnit (Enum)

| Value | Wire | Width |
|---|---|---|
| `Minute` | `m` | 1 minute |
| `Hour` | `h` | 60 minutes |
| `Day` | `d` | 1440 minutes |
| `Week` | `w` | 10080 minutes |
| `Month` | `M` | no fixed width |

Unit letters are **case-sensitive**: `m` is minutes, `M` is months.

### Properties

| Name | Type | Notes |
|---|---|---|
| `amount` | `Integer` | > 0 |
| `unit` | `SampleUnit` | |

Immutable; two sizes are equal when amount and unit are.

### Actions

| Action | Returns | Description |
|---|---|---|
| `Parse(text: String)` | `SampleSize` | Reads `^(\d+)([mhdwM])$` exactly (no spaces, case-sensitive). |
| `to_string()` | `String` | `"{amount}{unit wire}"`; `Parse` reads it back. |
| `can_be_resampled_from(source: SampleSize)` | `Boolean` | Whether bars of size `source` merge cleanly into bars of this size. Month from month: `self.amount % source.amount == 0`. Month from a fixed unit: `1440 % source_minutes == 0` (the source divides a day). Fixed unit from month: `false`. Fixed from fixed: `self_minutes % source_minutes == 0`. So `15m` from `5m` yes, `7m` from `5m` no, `1m` from `5m` no. |

### Errors

| Code | Description |
|---|---|
| `INVALID_INTERVAL` | Text not of the form amount + unit letter. Message: `invalid interval '{text}'; expected an integer amount plus a unit letter (m/h/d/w/M, case-sensitive), e.g. '5m', '4h', '7d', '2w', '3M'`. |
| `NON_POSITIVE_INTERVAL` | Amount is 0. Message: `interval amount must be positive, got '{text}'`. |

---

## 2. Symbol

*Python: `domain/market_data/symbol.py`.* The fixed specification of a tradeable instrument. It knows nothing about prices observed or strategies.

### SymbolCategory (Enum)

`FOREX` (`Forex`), `COMMODITY` (`Commodity`), `INDEX` (`Index`).

### Properties

| Name | Type | Notes |
|---|---|---|
| `name` | `String` | display name, "Euro / U.S. Dollar" |
| `ticker` | `String` | upper case, "EURUSD"; the registry key |
| `pip_size` | `Float` | price of one pip |
| `tick_size` | `Float` | price of one point (the smallest step) |
| `category` | `SymbolCategory` | |

Immutable.

### Actions

| Action | Returns | Description |
|---|---|---|
| `to_pips(price_diff: Float)` | `Float` | `price_diff / pip_size`. |
| `price_decimals` | `Integer` | Decimal places of `tick_size`, read from its exact decimal representation (0.00001 → 5, 0.001 → 3). Used to format and round prices. |

### The registry, `SYMBOLS: Map<String, Symbol>`

| Ticker | Name | Category | `pip_size` | `tick_size` |
|---|---|---|---|---|
| `EURUSD` | Euro / U.S. Dollar | Forex | 0.0001 | 0.00001 |
| `GBPUSD` | British Pound / U.S. Dollar | Forex | 0.0001 | 0.00001 |
| `AUDUSD` | Australian Dollar / U.S. Dollar | Forex | 0.0001 | 0.00001 |
| `NZDUSD` | New Zealand Dollar / U.S. Dollar | Forex | 0.0001 | 0.00001 |
| `USDCAD` | U.S. Dollar / Canadian Dollar | Forex | 0.0001 | 0.00001 |
| `USDCHF` | U.S. Dollar / Swiss Franc | Forex | 0.0001 | 0.00001 |
| `USDJPY` | U.S. Dollar / Japanese Yen | Forex | 0.01 | 0.001 |
| `XAUUSD` | Gold / U.S. Dollar | Commodity | 0.1 | 0.01 |
| `XAGUSD` | Silver / U.S. Dollar | Commodity | 0.01 | 0.001 |
| `DEUIDXEUR` | German 40 Index | Index | 1.0 | 0.001 |

`by_ticker(ticker: String) -> Symbol` looks a ticker up, case-insensitively. A new symbol is usable everywhere (configs, CLIs, `show_symbols`) once it is in the registry.

### Errors

| Code | Description |
|---|---|
| `UNKNOWN_SYMBOL` | No such ticker. Message: `unknown symbol ticker '{ticker}'`. |

---

## 3. Clocks (time zones)

*Python: `domain/market_data/broker_clock.py`.* Two of the sources run on clocks no IANA zone describes, so the application defines two kinds of `TimeZone` of its own. Any `TimeZone` must answer: the UTC offset at a wall-clock reading, and the wall-clock reading of an instant.

### ShiftedZone

A real zone's wall clock moved by a fixed amount: when `base` reads 17:00, this zone reads 17:00 + `shift`.

| Property | Type | Notes |
|---|---|---|
| `base` | `TimeZone` (IANA) | supplies offsets and daylight saving |
| `shift` | `Duration` | |
| `name` | `String` | display name |

- UTC offset at wall reading `w`: `base.offset(w − shift) + shift`. Daylight-saving dates, gaps and repeated hours all follow `base`, moved by `shift`.
- Wall reading of instant `i`: `base`'s wall reading of `i`, plus `shift`.
- Equal when `base` and `shift` are equal (the name doesn't count).

### SwitchingZone

One zone's rules until a wall-clock moment, another's from then on, for a source that changed its clock.

| Property | Type | Notes |
|---|---|---|
| `before` | `TimeZone` | rules for wall readings before `switch` |
| `after` | `TimeZone` | rules from `switch` on |
| `switch` | `LocalDateTime` | |
| `name` | `String` | |

- Invariant: `before` and `after` have the same UTC offset at `switch`, so the switch moves no clock. Error `INCONSISTENT_ZONE_SWITCH` otherwise.
- UTC offset at wall reading `w`: `before`'s if `w < switch`, else `after`'s.
- Wall reading of instant `i`: `after`'s reading; if that is before `switch`, `before`'s reading instead.
- Equal when `before`, `after` and `switch` are equal.

### The named clocks

| Constant | Definition | Display name (`to_string`) | Config/CLI name |
|---|---|---|---|
| `BROKER_SERVER_TZ` | `ShiftedZone(America/New_York, +7h)` | `broker-server (America/New_York+7h)` | `broker` |
| `HISTDATA_TZ` | `SwitchingZone(before: America/New_York, after: ShiftedZone(Europe/London, −5h, "Europe/London-5h"), switch: 2019-01-01 00:00)` | `histdata (America/New_York, from 2019 Europe/London-5h)` | `histdata` |

Why: the broker's server opens the FX week (Sunday 17:00 New York) at Monday 00:00, which makes it GMT+2 in winter and GMT+3 in summer, switching on the US daylight-saving dates. histdata.com's downloads are New York time with the EU switch dates from 2019 (London − 5h), plain New York time before. The evidence is in `CLAUDE.md`, "Gotchas".

### Actions

| Action | Returns | Description |
|---|---|---|
| `timezone_by_name(name: String)` | `TimeZone` | `BROKER_SERVER_TZ` for `broker`, `HISTDATA_TZ` for `histdata` (both trimmed, any case); otherwise the IANA zone `name` (case as IANA spells it). |
| `timezone_name(zone: TimeZone)` | `String` | The reverse: `broker`, `histdata`, the IANA key, or for any other zone its display name. |
| `is_utc(zone: TimeZone)` | `Boolean` | Offset is zero on both 2020-01-01 and 2020-07-01 (so a zone with daylight saving fails). |

An IANA zone's display name is its key (`UTC`, `Europe/London`).

### Errors

| Code | Description |
|---|---|
| `UNKNOWN_TIMEZONE` | Not `broker`, `histdata` or an IANA name (also an empty or malformed name). |
| `INCONSISTENT_ZONE_SWITCH` | `SwitchingZone` whose zones disagree at the switch. |

---

## 4. TimeWindow

*Python: `domain/market_data/time_window.py`.* A daily time-of-day window, each bound optional and in its own zone, so "08:00–16:00 London" stays London hours across daylight saving whatever clock the data is on. Used for `RsiDivergence`'s entry window.

### Properties

| Name | Type | Notes |
|---|---|---|
| `start` | `ZonedTime?` | inclusive |
| `end` | `ZonedTime?` | exclusive; may be in a different zone from `start` |

Invariant: a bound that is set has a zone (`ZONE_REQUIRED`).

### Actions

| Action | Returns | Description |
|---|---|---|
| `contains(instant: Instant)` | `Boolean` | See below. |

`contains`:

- **Both bounds:** let `D` be the instant's date in `start`'s zone. For `d` in (`D`, `D − 1 day`): the window opening on `d` runs from `d` at `start` (in `start`'s zone) to the first `end` after it: `d` at `end` (in `end`'s zone) if that is later than the opening, otherwise `d + 1` at `end`. The instant is inside if it falls in either window. So `end <= start` wraps past midnight (22:00–02:00), and `start == end` in one zone is a whole day.
- **Only `start`:** the instant's time of day in `start`'s zone is `>= start` (until midnight).
- **Only `end`:** the instant's time of day in `end`'s zone is `< end` (from midnight).
- **Neither:** always `true`.

A wall reading that falls in a daylight-saving gap or overlap resolves with the earlier offset (Python's `fold=0`).

### Errors

| Code | Description |
|---|---|
| `ZONE_REQUIRED` | A bound without a zone, or `contains` given a timestamp without one. |

---

## 5. TradingSession

*Python: `domain/market_data/trading_session.py`, `domain/market_data/trading_session_instance.py`.* A named daily session window, and one dated occurrence of it.

### TradingSession

| Property | Type | Notes |
|---|---|---|
| `start_time` | `ZonedTime` | |
| `end_time` | `ZonedTime` | may be in a different zone from `start_time` |
| `name` | `String?` | display name, and the key in `SESSIONS` |

Immutable. Invariant: both bounds have a zone (`ZONE_REQUIRED`).

| Action | Returns | Description |
|---|---|---|
| `start_time_on(date: Date)` | zoned date-time | `date` at `start_time`, in its own zone. |
| `end_time_on(date: Date)` | zoned date-time | `date` at `end_time`, in its own zone. |
| `start_time_utc_on(date: Date)` | `Instant` | `start_time_on(date)` as UTC. A date is needed: with daylight saving there is no single UTC start. |
| `end_time_utc_on(date: Date)` | `Instant` | Same for the end. |
| `create_session(date: Date)` | `TradingSessionInstance` | Start = `start_time_utc_on(date)`; end = `end_time_utc_on(date)`, or `end_time_utc_on(date + 1)` when that is not after the start (the session wraps past midnight). Compares instants, not wall times, since the bounds may be in different zones. |

### The standard sessions, `SESSIONS: Map<String, TradingSession>`

| Name | Window | Notes |
|---|---|---|
| `Tokyo` | 09:00–15:30 Asia/Tokyo | Tokyo Stock Exchange bells (lunch break ignored) |
| `Asia` | 09:00–18:00 Asia/Tokyo | the informal FX Asia session, 00:00–09:00 UTC |
| `London` | 08:00–16:30 Europe/London | London Stock Exchange bells |
| `New York` | 09:30–16:00 America/New_York | NYSE bells |

A config's `TradingSession` strategy parameter and `calculate_daily_sessions --session` take these names.

### TradingSessionInstance

One dated session window.

| Property | Type | Notes |
|---|---|---|
| `start_dt` | `Instant` | |
| `end_dt` | `Instant` | exclusive |

| Action | Returns | Description |
|---|---|---|
| `start_dt_utc()`, `end_dt_utc()` | `Instant` | The bounds in UTC. |
| `contains(dt)` | `Boolean` | `start <= dt < end`. A timestamp without a zone is taken as UTC. |

The Python class also accumulates bars (`add(bar) -> Boolean`, adding only bars it `contains`, plus `bar_block`, `range`, `mid`, `high_value`, `low_value`, `bar_count` delegating to a `BarBlock`). Nothing in the application uses that part today; only `create_session`'s bounds are used.

---

## 6. Bar and BarBlock

*Python: `domain/bar_approach/bar.py`, `bar_block.py`.* One candle as an object, and many candles folded into one span. The application works on bar tables; `Bar` is what the MT5 port's streaming reader produces, which no use case calls today. Port it only if you want that reader.

### Bar

| Property | Type | Notes |
|---|---|---|
| `dt` | `LocalDateTime` | open time |
| `open`, `high`, `low`, `close` | `Float` | |
| `tick_volume` | `Integer = 0` | |
| `real_volume` | `Integer = 0` | the table's `volume` column |
| `spread` | `Integer?` | points |

Immutable.

| Action | Returns | Description |
|---|---|---|
| `date`, `time` | `Date`, `LocalTime` | parts of `dt` |
| `range` | `Float` | `abs(high − low)` |
| `body_range` | `Float` | `abs(close − open)` |
| `is_bullish` | `Boolean` | `close > open` |
| `midpoint` | `Float` | `(high + low) / 2` |
| `contains(price)` | `Boolean` | `low <= price <= high` |
| `is_partially_above_or_equal(price)` | `Boolean` | `high >= price` |
| `is_partially_below_or_equal(price)` | `Boolean` | `low <= price` |
| `is_completely_above_or_equal(price)` | `Boolean` | `low >= price` |
| `is_completely_below_or_equal(price)` | `Boolean` | `high <= price` |

### BarBlock

Bars folded into one OHLC span as they arrive. Empty until the first `add`.

| Property | Type | Notes |
|---|---|---|
| `first_dt` | `LocalDateTime?` | `dt` of the first bar added |
| `open_value`, `open_dt` | `Float?`, `LocalDateTime?` | of the earliest `dt` seen |
| `close_value`, `close_dt` | `Float?`, `LocalDateTime?` | of the latest `dt` seen |
| `high_value`, `high_dt` | `Float = −∞`, `LocalDateTime?` | |
| `low_value`, `low_dt` | `Float = +∞`, `LocalDateTime?` | |
| `bar_count` | `Integer = 0` | |

| Action | Returns | Description |
|---|---|---|
| `add(bar: Bar)` | `Void` | Folds one bar in. Open/close follow the earliest/latest `dt`, not arrival order; a new high (strictly greater) or low (strictly less) replaces the old one. |
| `day` | `Date?` | date of `first_dt` |
| `range` | `Float` | `high_value − low_value` |
| `mid` | `Float` | `(high_value + low_value) / 2` |

---

## 7. Bar table operations

*Python: `domain/market_data/frames.py`, `shift_timezone.py`, `session_ohlc.py`.* What happens to a bar table between reading it and backtesting it.

### `clean_frame(table) -> Table<BarRow>`

Stable-sort by `datetime`, then drop rows whose `datetime` repeats an earlier row's, keeping the **last** of them. Because the sort is stable, among rows sharing a timestamp the one that came later in the input wins.

### `resample_ohlc(table, timeframe: SampleSize) -> Table<BarRow>`

Collapses a clean table onto a coarser grid.

1. Assign every bar to the grid bucket containing its `datetime` (buckets are half-open).
2. Aggregate each bucket: `open` first, `high` max, `low` min, `close` last, `tick_volume` sum, `volume` sum, `spread` mean (ignoring nulls). Only the columns present are aggregated; other columns are dropped.
3. Drop buckets with no bar (no gap rows are emitted).
4. Label each bar by its bucket's **start**.

The grid, by unit (all on the naive timestamps, so daylight saving plays no part):

| Unit | Buckets |
|---|---|
| minutes, hours, days | `origin + k × width` for every integer `k`, where `origin` is midnight of the first bar's date. The grid does **not** restart each day: `5h` buckets run 00:00, 05:00, 10:00, 15:00, 20:00, 01:00 (next day), … |
| weeks | `origin + k × width`, with `origin` the Monday **1969-12-29 00:00**, so a week is labelled by its Monday and `2w` pairs the same weeks whatever the data's first day |
| months | calendar months; a bucket of `n` months starts on the 1st, the first one at the first bar's month, then every `n` months |

An empty input gives an empty table.

The Python function also accepts broker labels (`M1`, `M5`, `M15`, `M30`, `H1` = `1m`, `5m`, `15m`, `30m`, `1h`) and passes any other string to pandas as a raw rule. A rewrite should take a `SampleSize` only, and map broker labels at the caller.

### `shift_timezone(table, to_tz: TimeZone, from_tz: TimeZone = BROKER_SERVER_TZ) -> Table<BarRow>`

Re-expresses `datetime` on another clock: each value is read as a wall-clock reading on `from_tz`, converted to the instant, and written back as the wall-clock reading on `to_tz`, still without a zone. Every other column is unchanged.

A reading that does not exist on `from_tz` (a daylight-saving gap) or exists twice (an overlap) is an error, `TIMESTAMP_NOT_IN_ZONE`. The sources have no bars at those hours in practice (they fall on weekends).

### `session_ohlc(table, session: TradingSession, timezone: TimeZone) -> Table<SessionOhlcRow>`

The open, high, low and close of `session` on every day, from a bar table on the `timezone` clock (which labels it; nothing is shifted in the result).

`SessionOhlcRow`:

| Column | Type | Notes |
|---|---|---|
| `date` | `Date` | the session day |
| `open` | `Float` | open of the first bar in the window |
| `high` | `Float` | max high |
| `low` | `Float` | min low |
| `close` | `Float` | close of the last bar |
| `bar_count` | `Integer` | bars in the window |

Steps:

1. Stable-sort the bars by `datetime` (the input need not be clean).
2. For each bar, compute its instant, and its date `T` on the session's start zone.
3. A bar's session day is `T` if `session.create_session(T)` contains its instant, else `T − 1` if `create_session(T − 1)` does, else it has none and is ignored. (`T` wins when both do.) So a session crossing midnight belongs to the day it opens.
4. Group the bars by session day and aggregate as in the table; one row per day with at least one bar, oldest first.

An empty input gives an empty table with these columns.

---

## 8. HistoricalData

*Python: `domain/market_data/historical_data.py`.* The bars a backtest runs on: a clean bar table plus what it takes to interpret it.

### SpreadUnit (Enum)

The unit a source table's `spread` column is in: `PIPS` (`pips`), `POINTS` (`points`, MetaTrader), `PRICE` (`price`, ask − bid, Dukascopy).

### Properties

| Name | Type | Notes |
|---|---|---|
| `data` | `Table<BarRow>` | must not be changed after construction |
| `timeframe` | `SampleSize` | the bar size |
| `symbol` | `Symbol` | |
| `timezone` | `TimeZone = BROKER_SERVER_TZ` | the clock of `data.datetime` |

Invariants, checked on construction, which **never changes the table**: a wrong table fails instead of being fixed quietly.

| Rule | Error |
|---|---|
| columns `datetime`, `open`, `high`, `low`, `close` exist | `MISSING_COLUMNS` (`historical data is missing required column(s): [...]`) |
| at least one row | `NO_BARS` (`historical data has no bars`) |
| `datetime` is a zone-less timestamp column | `DATETIME_NOT_NAIVE` |
| `datetime` strictly increasing | `NOT_STRICTLY_INCREASING` (`'datetime' must be strictly increasing -- run domain.market_data.frames.clean_frame first`) |
| `open`/`high`/`low`/`close` are `Float` with no nulls | `OHLC_NOT_FLOAT`, `OHLC_MISSING` |
| `tick_volume`/`volume`, if present, are `Integer?` | `VOLUME_NOT_INTEGER` |
| `spread`, if present, is `Float?` (pips) | `SPREAD_NOT_FLOAT` |

### Actions

| Action | Returns | Description |
|---|---|---|
| `from_frame(table, timeframe, symbol, spread_unit: SpreadUnit = PIPS, timezone = BROKER_SERVER_TZ)` | `HistoricalData` | Normalises a copy of a reader's table, then constructs (and so validates). OHLC become `Float`; volumes become `Integer?` (a fractional value is `NON_INTEGRAL_VOLUME`, never rounded); spread becomes pips: unchanged for `PIPS`, `symbol.to_pips(spread × tick_size)` for `POINTS`, `symbol.to_pips(spread)` for `PRICE`. It does not sort or deduplicate: a table that needs it fails validation. |
| `start_dt` | `LocalDateTime` | first bar's `datetime` |
| `end_dt` | `LocalDateTime` | last bar's `datetime` (its open time) |
| `length` | `Integer` | number of bars |
| `summary()` | `DataSummary` | what the bars cover, without them: `symbol`, `timeframe`, `timezone`, `first_bar` (= `start_dt`), `last_bar` (= `end_dt`), `bars` (= `length`). How a [BacktestResult](backtesting.md#backtestresult) describes its data. |
| `locate(stamps: List<LocalDateTime?>)` | `List<Integer>` | For each stamp, the index of the bar it falls in: the last bar whose `datetime <= stamp`. `−1` for a stamp before the first bar, or `null`. |

---

## 9. Legacy, not needed for a rewrite

*Python: `domain/bar_approach/`.* The engine of a standalone script that has since been replaced by the `SessionBreakout` plugin. It is kept in the Python repo on purpose, but no use case uses it, so a rewrite can leave it out:

| Item | What it was |
|---|---|
| `BarChunks` | splits a `Stream<Bar>` into monthly/yearly runs in constant memory |
| `shift_bars` | `shift_timezone` for a `Stream<Bar>` |
| `DailySessionBase`, `DailyStrategyBase` | a bar-by-bar daily session lifecycle (create a session per day, feed it bars, force-close at its end) |
| `position.Position`, `PendingPosition`, `Outcome` | the script's own position model; the application's is in [backtesting.md](backtesting.md#2-position) |
