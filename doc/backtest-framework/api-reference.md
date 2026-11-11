# Backtest Framework — API Reference

A companion to the [framework overview](README.md). For how these pieces fit together, see [Running a backtest](running-a-backtest.md) and [Writing a new strategy](writing-a-strategy.md).

## Contents

1. [Data](#1-data)
2. [Positions](#2-positions)
3. [Strategies](#3-strategies)
4. [Costs, results, the backtest](#4-costs-results-the-backtest)
5. [Application and ports (files, provenance)](#5-application-and-ports-files-provenance)

---

Only the public names are listed. Everything below `domain/` performs no I/O.

## 1. Data

### `domain.market_data.historical_data`

**`HistoricalData(data, timeframe, symbol, timezone=BROKER_SERVER_TZ)`**: bars for one symbol at one timeframe. Frozen; don't modify `data` in place.

| Field | Type | Meaning |
|---|---|---|
| `data` | `pd.DataFrame` | one row per bar (layout below) |
| `timeframe` | `SampleSize` | bar size, e.g. `SampleSize.Parse("5m")` |
| `symbol` | `Symbol` | pip size and price precision |
| `timezone` | `tzinfo` | the clock of `datetime` (default: broker server) |

Frame layout:

| Column | Type | Required |
|---|---|---|
| `datetime` | naive `datetime64`, strictly increasing | yes |
| `open`, `high`, `low`, `close` | `float64`, bid, no missing values | yes |
| `tick_volume`, `volume` | integer (`Int64` allowed) | no |
| `spread` | `float64`, **in pips** | no |

Extra columns are kept. The constructor only **validates**, and raises `ValueError` with a hint. For unsorted or duplicate timestamps, the hint is to run `domain.market_data.frames.clean_frame` first.

| Member | Returns |
|---|---|
| `HistoricalData.from_frame(frame, timeframe, symbol, *, spread_unit=SpreadUnit.PIPS, timezone=BROKER_SERVER_TZ)` | a new instance from a copy of `frame`, after normalising it: OHLC → float, whole-number float volumes → `Int64` (fractional volumes raise), spread → pips. It does not sort or deduplicate. |
| `start_dt`, `end_dt` | first and last bar timestamps (bar open times) |
| `len(data)` | number of bars |
| `summary()` | a `DataSummary` (frozen): `symbol`, `timeframe`, `timezone`, `first_bar`, `last_bar`, `bars`, the same facts without the frame; what `BacktestResult.data` holds |
| `locate(stamps)` | NumPy array: for each timestamp, the row of the bar it falls in (the last bar opening at or before it); `-1` when before the first bar or missing |

**`SpreadUnit`**: the unit of a source's `spread` column: `PIPS`, `POINTS` (multiples of tick size, MT5), `PRICE` (ask − bid, Dukascopy).

### `domain.market_data.sample_size`

**`SampleSize(amount, unit)`**: a bar size. `SampleSize.Parse("15m")` builds one: `m` minutes, `h` hours, `d` days, `w` weeks, `M` months (case-sensitive). `str(size)` gives `"15m"` back, and `size.to_pandas_rule()` gives the pandas resample rule (`"15min"`; weeks are hours, `"1w"` → `"168h"`, resampled from a Monday so each week is labelled by its Monday).

### `domain.market_data.symbol`

**`Symbol`**: an instrument's constants: `ticker`, `pip_size`, `tick_size`, `to_pips(price_diff)`, `price_decimals`. Instances: `EURUSD`, `GBPUSD`, `USDJPY`, `XAUUSD`, …, all in `SYMBOLS` by ticker; `by_ticker("EURUSD")` looks one up.

### `domain.market_data.broker_clock`

| Name | Meaning |
|---|---|
| `BROKER_SERVER_TZ` | the MT5 server clock, New York + 7h |
| `HISTDATA_TZ` | histdata.com's clock: `America/New_York` before 2019-01-01, London − 5h (New York's clock on the EU daylight-saving dates) from then on |
| `SwitchingZone(before, after, switch, name)` | a `tzinfo`: `before`'s rules until the wall-clock moment `switch`, `after`'s from it on; both must agree on the UTC offset at `switch` |
| `ShiftedZone(base, shift, name)` | a `tzinfo`: `base`'s wall clock moved by `shift` |
| `timezone_by_name(name)` | `"broker"` → `BROKER_SERVER_TZ`, `"histdata"` → `HISTDATA_TZ`, otherwise `ZoneInfo(name)` |
| `timezone_name(zone)` | the inverse: `BROKER_SERVER_TZ` → `"broker"`, `HISTDATA_TZ` → `"histdata"`, a `ZoneInfo` → its IANA key |

pandas rejects custom `tzinfo` objects, so don't pass `BROKER_SERVER_TZ` to `tz_localize`; use `shift_timezone`.

### `domain.market_data.time_window`

**`TimeWindow(start=None, end=None)`**: a daily `[start, end)` window. Each bound is a timezone-aware `datetime.time` or `None` (open). `window.contains(instant)` takes a timezone-aware `datetime`. An `end` at or before `start` wraps past midnight, and the bounds may be in different zones. **`ZonedTime`** is the annotation for a strategy field holding such a bound; the config reads it as `"HH:MM <zone>"`.

**`TradingSession(start_time, end_time, name=None)`** (`domain.market_data.trading_session`): a session's daily window, each bound a timezone-aware `datetime.time`; `create_session(date)` resolves one date's window to UTC, the end on the next day when it wraps past midnight. The standard ones are `TOKYO_SESSION`, `ASIA_SESSION`, `LONDON_SESSION` and `NEW_YORK_SESSION`, collected by name in `SESSIONS`. A strategy field typed `TradingSession` (ORB's `session`) is set from a config by a `SESSIONS` name.

### `domain.market_data.shift_timezone`

**`shift_timezone(frame, to_tz, *, from_tz=BROKER_SERVER_TZ)`**: returns a copy of `frame` with `datetime` re-expressed from `from_tz` to `to_tz`, still naive.

## 2. Positions

### `domain.backtesting.side`

**`Side`**: `LONG` (`"long"`), `SHORT` (`"short"`).

### `domain.backtesting.position`

**`PositionOutcome`**:

| Member | Value | Meaning |
|---|---|---|
| `OPEN` | `open` | not closed yet (what a strategy returns) |
| `STOP_LOSS_HIT` | `stop-loss-hit` | SL reached first |
| `TAKE_PROFIT_HIT` | `take-profit-hit` | TP reached first |
| `MANUAL_CLOSE` | `manual-close` | closed at its time stop |
| `END_OF_DATA` | `end-of-data` | still open when the bars ran out |
| `AMBIGUOUS` | `ambiguous` | one bar touched both SL and TP (with `EXCLUDE`); no price |

**`EntryFill`**: where in its entry bar a position filled, which decides whether that bar can hit SL/TP.

| Member | Value | Meaning |
|---|---|---|
| `AT_LEVEL` | `at-level` | at a price inside the bar (stop/limit order, break, re-cross); SL/TP are checked from the next bar |
| `AT_OPEN` | `at-open` | at the bar's open; the entry bar is checked too |

**`Position(open_dt, open_price, side, sl, tp, entry_fill=AT_LEVEL, exit_dt=None, close_dt=None, close_price=None, outcome=OPEN, tag="")`**: one trade. Prices are raw price units, not pips.

- Construction validates: long `sl < open_price < tp`, short `tp < open_price < sl`, and `exit_dt` after `open_dt`.
- `is_closed` → whether `outcome` is no longer `OPEN`.
- `close(at, price, outcome)` → records the close. Called by the simulator, not by strategies. It closes once only; `price` must be `None` exactly when `outcome` is `AMBIGUOUS`.

**`positions_to_frame(positions)`** → a DataFrame with the columns `FRAME_COLUMNS` (`open_dt, side, open_price, sl, tp, entry_fill, exit_dt, close_dt, close_price, outcome, tag`). Enums become their string values. An empty list gives an empty frame with the same columns and dtypes.

## 3. Strategies

### `domain.backtesting.trading_strategy`

**`TradingStrategy`** (abstract): see [the contract](writing-a-strategy.md#1-the-contract) in *Writing a new strategy*.

| Member | Required | Default |
|---|---|---|
| `generate_positions(data) -> list[Position]` | yes | – |
| `name` (property) | no | class name |
| `parameters() -> dict` | no | dataclass fields (a dataclass-valued field, such as a `TradingSession`, stays an object), else `{}` |
| `split_days(data) -> Iterable[date]` | no | every calendar day with a bar |

### `strategies`

**`STRATEGIES`**: `dict[str, type[TradingStrategy]]`, the names a `backtest.py` config's `strategy.name` accepts.

## 4. Costs, results, the backtest

### `domain.backtesting.cost_model`

**`CostModel`** (abstract): `cost_pips(trades, data) -> pd.Series`, one round-trip cost in pips per row of a positions frame, aligned to its index. Subclass it to model other frictions. `notes(trades, data) -> list[str]` (none by default) is what the report should warn about how the trades were charged; `Backtest.run` puts them in `BacktestResult.notes`. `parameters() -> dict` is what describes it in `run.json` and the report: a dataclass cost model's fields, else `{}` (override for anything else).

| Class | Parameters | Charges |
|---|---|---|
| `FixedCost(pips=1.7)` | `pips ≥ 0` | the same cost for every trade |
| `SpreadCost(commission_pips=0.0)` | `commission_pips ≥ 0` | the `spread` of the entry bar (long) or exit bar (short), plus the commission. Raises if the data has no `spread` column. A trade on a bar without a spread value is charged 0 spread, and `notes` lists it. |

### `domain.backtesting.trade_results`

**`trade_results(trades, symbol, cost_pips) -> pd.DataFrame`**: a copy of a positions frame with `RESULT_COLUMNS` appended: `gross_pips, cost_pips, net_pips, risk_pips, net_r, duration_min`. Trades without a close price (ambiguous or open) get NaN P&L.

### `domain.backtesting.splits`

- **`SplitMode`**: `NONE` (`"none"`), `DVT` (`"dvt"`), `MONTHLY` (`"monthly"`), `YEARLY` (`"yearly"`). How `Backtest` groups trades.
- **`split_labels(dates, mode) -> dict[date, str]`**: each distinct date's split name, in chronological order: `split_dates`'s cut for `DVT`, `"2024-03"` for `MONTHLY`, `"2024"` for `YEARLY`. Raises for `NONE`.
- **`Split`**: `DISCOVERY`, `VALIDATION`, `TEST`.
- **`split_dates(dates, *, discovery=0.60, validation=0.20) -> dict[date, Split]`**: sorts the distinct dates and cuts them chronologically. The boundaries are identical to the research scripts' `split_dates`.
- **`assign_splits(open_dts, by_date: dict[date, str]) -> pd.Series`**: the split name of each trade from the date it opens on. Raises if a date isn't covered.

### `domain.backtesting.statistics`

- **`compute_statistics(trades) -> dict`**: every metric in [`statistics.csv`](reading-the-backtest-results.md#statisticscsv) in *Reading the backtest results*, in report order.
- **`statistics_by_split(trades, splits=()) -> pd.DataFrame`**: one row for `all`, then one per name in `splits`, in that order (a split without trades gets a row of zeros).
- **`split_verdict(table) -> SplitVerdict`**: the verdict on a `statistics_by_split` table's splits (every row after `all`). **`SplitVerdict`** (frozen) has `splits`, `traded` (those with trades) and `net_positive` (those with `total_net_pips > 0`), each a tuple of split names in table order, and `holds_in_every_split`: every split is net positive, those without trades included.
- **`max_drawdown(net_pips)`**, **`max_consecutive_losses(net_pips)`**: the two building blocks, usable on any sequence.

### `domain.backtesting.backtest`

**`Backtest(strategy, data, cost_model=FixedCost(), ambiguity_policy=AmbiguityPolicy.EXCLUDE, splits=SplitMode.NONE)`**: one strategy, one dataset, one set of rules.

- `run() -> BacktestResult`: a pure calculation, with no files, clock or git. It closes every position the strategy returned under the rules in [How a backtest decides things](README.md#how-a-backtest-decides-things) (in the private `_simulate`, the one place exits are decided), then applies costs, splits and statistics. It raises `ValueError` on a position that is already closed or that opens before the first bar; these are never skipped silently.

- **`AmbiguityPolicy`**: `EXCLUDE` (`"exclude"`), `ASSUME_SL` (`"assume-sl"`), `ASSUME_TP` (`"assume-tp"`).

**`BacktestResult(strategy, data, cost_model, ambiguity_policy, splits, trades, statistics, verdict, notes=())`** (frozen): what ran, on what, under which rules, and what it produced, so it can be reported on its own.

- `strategy`, `cost_model`, `ambiguity_policy`, `splits`: the `Backtest`'s own.
- `data`: `data.summary()`, a `DataSummary` (symbol, timeframe, timezone, first and last bar, bar count) rather than the bars.
- `trades`: the positions frame with its result columns (and `split`, unless `SplitMode.NONE`), sorted by `open_dt`.
- `statistics`: the `statistics_by_split` table: `all`, then one row per split in chronological order.
- `verdict`: `split_verdict(statistics)`, a `SplitVerdict`; `None` with `SplitMode.NONE`.
- `notes`: the cost model's `notes`, printed at the end of the report and recorded in `run.json`.

## 5. Application and ports (files, provenance)

### `application.load_historical_data_use_case`

| Function | Reads |
|---|---|
| `load_mt5(source, timeframe, symbol, *, timezone, progress=None)` | a folder of MT5 exports or one export; resampled per file and deduplicated across files |
| `load_histdata(source, timeframe, symbol, *, timezone, progress=None)` | a folder of histdata.com MetaTrader downloads (`DAT_MT_*.csv`, the `.txt` gap reports ignored) or one download; built like `load_mt5`; no volume or spread columns; `timezone` must keep New York's clock (`ValueError` otherwise) |
| `load_dukascopy(source, timeframe, symbol, *, timezone, progress=None)` | Dukascopy bid/ask pairs under a folder (recursively), or the pair one file belongs to; pairs match on instrument and start date; no volume columns; `timezone` must be UTC (`ValueError` otherwise) |
| `load_source(source, source_format, timeframe, symbol, *, timezone, progress=None)` | the loader for `source_format`, a `SourceFormat`: `METATRADER` → `load_mt5`, `HISTDATA` → `load_histdata`, `DUKASCOPY` → `load_dukascopy` |

All return a `HistoricalData` resampled to `timeframe`, labelled with the required `timezone` (the clock the source is on; never assumed, never shifted). Pass `progress=print` to see one line per file.

### `ports.backtest_result_access`

Formats a `BacktestResult` and writes the four result files; layouts in [Reading the backtest results](reading-the-backtest-results.md).

- **`RunProvenance(created, git, source=None, strategy_name=None)`** (frozen): what the record holds beyond the result. `created` (a `datetime`) and `git` (a `GitCommit`) come from `ports.run_environment.now()` and `git_commit()`; `source` is recorded as `run.json`'s `source`; `strategy_name` is the name the strategy is reported under, its own `name` (its class name by default) when `None`.
- **`write_results(result, provenance, out_dir) -> list[Path]`**: creates `out_dir` if needed and writes, overwriting, `positions.csv` (prices rounded to the symbol's precision, pips to 2 places), `statistics.txt`, `statistics.csv` and `run.json`, returned in that order.
- **`format_report(result, provenance) -> str`**: the `statistics.txt` text; writes nothing.
- **`run_info(result, provenance) -> dict`**: the `run.json` content; writes nothing.

### `backtest` (the CLI module, importable)

- **`run_backtest(backtest, out_dir, *, source=None, strategy_name=None, now=ports.run_environment.now, git_commit=ports.run_environment.git_commit) -> BacktestRun`**: runs the backtest, records a `RunProvenance` and writes the four files with `write_results`. `strategy_name` is recorded as `run.json`'s `strategy.name` and shown in the report header; the CLI passes the config's `strategy.name`. `now` and `git_commit` are the clock and the repo state recorded as `created` and `git`; pass fakes for a deterministic `run.json`. `BacktestRun` has `result`, `provenance`, `paths` and `report` (the `statistics.txt` text, from `format_report`).
