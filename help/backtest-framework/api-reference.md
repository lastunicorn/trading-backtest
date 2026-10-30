# Backtest Framework — API Reference

A companion to the [framework overview](README.md). For how these pieces fit together, see [Running a backtest](running-a-backtest.md) and [Writing a new strategy](writing-a-strategy.md).

## Contents

1. [Data](#1-data)
2. [Positions](#2-positions)
3. [Strategies](#3-strategies)
4. [Costs, results, the backtest](#4-costs-results-the-backtest)
5. [Application (files, provenance)](#5-application-files-provenance)

---

Only the public names are listed. Everything below `domain/` performs no I/O.

## 1. Data

### `domain.pandas_approach.historical_data`

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

Extra columns are kept. The constructor only **validates**, and raises `ValueError` with a hint. For unsorted or duplicate timestamps, the hint is to run `domain.pandas_approach.frames.clean_frame` first.

| Member | Returns |
|---|---|
| `HistoricalData.from_frame(frame, timeframe, symbol, *, spread_unit=SpreadUnit.PIPS, timezone=BROKER_SERVER_TZ)` | a new instance from a copy of `frame`, after normalising it: OHLC → float, whole-number float volumes → `Int64` (fractional volumes raise), spread → pips. It does not sort or deduplicate. |
| `start_dt`, `end_dt` | first and last bar timestamps (bar open times) |
| `len(data)` | number of bars |
| `locate(stamps)` | NumPy array: for each timestamp, the row of the bar it falls in (the last bar opening at or before it); `-1` when before the first bar or missing |

**`SpreadUnit`**: the unit of a source's `spread` column: `PIPS`, `POINTS` (multiples of tick size, MT5), `PRICE` (ask − bid, Dukascopy).

### `domain.sample_size`

**`SampleSize(amount, unit)`**: a bar size. `SampleSize.Parse("15m")` builds one: `m` minutes, `h` hours, `d` days, `w` weeks, `M` months (case-sensitive). `str(size)` gives `"15m"` back, and `size.to_pandas_rule()` gives the pandas resample rule (`"15min"`).

### `domain.symbol`

**`Symbol`**: an instrument's constants: `ticker`, `pip_size`, `tick_size`, `to_pips(price_diff)`, `price_decimals`. Concrete classes: `EurUsd()`, `GbpUsd()`, `UsdJpy()`, `XauUsd()`, …; `by_ticker("EURUSD")` looks one up.

### `domain.broker_clock`

| Name | Meaning |
|---|---|
| `BROKER_SERVER_TZ` | the MT5 server clock, New York + 7h |
| `ShiftedZone(base, shift, name)` | a `tzinfo`: `base`'s wall clock moved by `shift` |
| `timezone_by_name(name)` | `"broker"` → `BROKER_SERVER_TZ`, otherwise `ZoneInfo(name)` |
| `timezone_name(zone)` | the inverse: `BROKER_SERVER_TZ` → `"broker"`, a `ZoneInfo` → its IANA key |

pandas rejects custom `tzinfo` objects, so don't pass `BROKER_SERVER_TZ` to `tz_localize`; use `shift_timezone`.

### `domain.time_window`

**`TimeWindow(start=None, end=None)`**: a daily `[start, end)` window. Each bound is a timezone-aware `datetime.time` or `None` (open). `window.contains(instant)` takes a timezone-aware `datetime`. An `end` at or before `start` wraps past midnight, and the bounds may be in different zones. **`ZonedTime`** is the annotation for a strategy field holding such a bound; the config reads it as `"HH:MM <zone>"`.

### `domain.pandas_approach.shift_timezone`

**`shift_timezone(frame, to_tz, *, from_tz=BROKER_SERVER_TZ)`**: returns a copy of `frame` with `datetime` re-expressed from `from_tz` to `to_tz`, still naive.

## 2. Positions

### `domain.pandas_approach.side`

**`Side`**: `LONG` (`"long"`), `SHORT` (`"short"`).

### `domain.pandas_approach.position`

**`PositionOutcome`**:

| Member | Value | Meaning |
|---|---|---|
| `OPEN` | `open` | not closed yet (what a strategy returns) |
| `STOP_LOSS_HIT` | `stop-loss-hit` | SL reached first |
| `TAKE_PROFIT_HIT` | `take-profit-hit` | TP reached first |
| `MANUAL_CLOSE` | `manual-close` | closed at its time stop |
| `END_OF_DATA` | `end-of-data` | still open when the bars ran out |
| `AMBIGUOUS` | `ambiguous` | one bar touched both SL and TP (with `EXCLUDE`); no price |

**`Position(open_dt, open_price, side, sl, tp, exit_dt=None, close_dt=None, close_price=None, outcome=OPEN, tag="")`**: one trade. Prices are raw price units, not pips.

- Construction validates: long `sl < open_price < tp`, short `tp < open_price < sl`, and `exit_dt` after `open_dt`.
- `is_closed` → whether `outcome` is no longer `OPEN`.
- `close(at, price, outcome)` → records the close. Called by the simulator, not by strategies. It closes once only; `price` must be `None` exactly when `outcome` is `AMBIGUOUS`.

**`positions_to_frame(positions)`** → a DataFrame with the columns `FRAME_COLUMNS` (`open_dt, side, open_price, sl, tp, exit_dt, close_dt, close_price, outcome, tag`). Enums become their string values. An empty list gives an empty frame with the same columns and dtypes.

## 3. Strategies

### `domain.pandas_approach.trading_strategy`

**`TradingStrategy`** (abstract): see [the contract](writing-a-strategy.md#1-the-contract) in *Writing a new strategy*.

| Member | Required | Default |
|---|---|---|
| `generate_positions(data) -> list[Position]` | yes | – |
| `name` (property) | no | class name |
| `parameters() -> dict` | no | dataclass fields, else `{}` |
| `split_days(data) -> Iterable[date]` | no | every calendar day with a bar |

### `strategies`

**`STRATEGIES`**: `dict[str, type[TradingStrategy]]`, the names a `backtest.py` config's `strategy` key accepts.

## 4. Costs, results, the backtest

### `domain.pandas_approach.cost_model`

**`CostModel`** (abstract): `cost_pips(trades, data) -> pd.Series`, one round-trip cost in pips per row of a positions frame, aligned to its index. Subclass it to model other frictions.

| Class | Parameters | Charges |
|---|---|---|
| `FixedCost(pips=1.7)` | `pips ≥ 0` | the same cost for every trade |
| `SpreadCost(commission_pips=0.0)` | `commission_pips ≥ 0` | the `spread` of the entry bar (long) or exit bar (short), plus the commission. Raises if the data has no `spread` column or a trade falls on a bar without one. |

### `domain.pandas_approach.trade_results`

**`trade_results(trades, symbol, cost_pips) -> pd.DataFrame`**: a copy of a positions frame with `RESULT_COLUMNS` appended: `gross_pips, cost_pips, net_pips, risk_pips, net_r, duration_min`. Trades without a close price (ambiguous or open) get NaN P&L.

### `domain.pandas_approach.splits`

- **`SplitMode`**: `NONE` (`"none"`), `DVT` (`"dvt"`), `MONTHLY` (`"monthly"`), `YEARLY` (`"yearly"`). How `Backtest` groups trades.
- **`split_labels(dates, mode) -> dict[date, str]`**: each distinct date's split name, in chronological order: `split_dates`'s cut for `DVT`, `"2024-03"` for `MONTHLY`, `"2024"` for `YEARLY`. Raises for `NONE`.
- **`Split`**: `DISCOVERY`, `VALIDATION`, `TEST`.
- **`split_dates(dates, *, discovery=0.60, validation=0.20) -> dict[date, Split]`**: sorts the distinct dates and cuts them chronologically. The boundaries are identical to the research scripts' `split_dates`.
- **`assign_splits(open_dts, by_date: dict[date, str]) -> pd.Series`**: the split name of each trade from the date it opens on. Raises if a date isn't covered.

### `domain.pandas_approach.statistics`

- **`compute_statistics(trades) -> dict`**: every metric in [`statistics.csv`](reading-the-backtest-results.md#statisticscsv) in *Reading the backtest results*, in report order.
- **`statistics_by_split(trades, splits=()) -> pd.DataFrame`**: one row for `all`, then one per name in `splits`, in that order (a split without trades gets a row of zeros).
- **`max_drawdown(net_pips)`**, **`max_consecutive_losses(net_pips)`**: the two building blocks, usable on any sequence.

### `domain.pandas_approach.backtest`

**`Backtest(strategy, data, cost_model=FixedCost(), ambiguity_policy=AmbiguityPolicy.EXCLUDE, position_resolve_delay=PositionResolveDelay.NEXT_BAR, splits=SplitMode.NONE)`**: one strategy, one dataset, one set of rules.

- `run() -> BacktestResult`: a pure calculation, with no files, clock or git. It closes every position the strategy returned under the rules in [How a backtest decides things](README.md#how-a-backtest-decides-things) (in the private `_simulate`, the one place exits are decided), then applies costs, splits and statistics. It raises `ValueError` on a position that is already closed or that opens before the first bar; these are never skipped silently.

- **`AmbiguityPolicy`**: `EXCLUDE` (`"exclude"`), `ASSUME_SL` (`"assume-sl"`), `ASSUME_TP` (`"assume-tp"`).
- **`PositionResolveDelay`**: `NEXT_BAR` (`"next-bar"`), `ENTRY_BAR` (`"entry-bar"`).

**`BacktestResult(trades, statistics)`** (frozen):

- `trades`: the positions frame with its result columns (and `split`, unless `SplitMode.NONE`), sorted by `open_dt`.
- `statistics`: the `statistics_by_split` table: `all`, then one row per split in chronological order.

## 5. Application (files, provenance)

### `application.load_historical_data_use_case`

| Function | Reads |
|---|---|
| `load_mt5(source, timeframe, symbol, *, timezone, progress=None)` | a folder of MT5 exports or one export; resampled per file and deduplicated across files |
| `load_dukascopy(source, timeframe, symbol, *, timezone, progress=None)` | Dukascopy bid/ask pairs under a folder (recursively), or the pair one file belongs to; pairs match on instrument and start date; no volume columns; `timezone` must be UTC (`ValueError` otherwise) |
| `load_source(source, source_format, timeframe, symbol, *, timezone, progress=None)` | the loader for `source_format`, a `SourceFormat`: `METATRADER` → `load_mt5`, `DUKASCOPY` → `load_dukascopy` |

All return a `HistoricalData` resampled to `timeframe`, labelled with the required `timezone` (the clock the source is on; never assumed, never shifted). Pass `progress=print` to see one line per file.

### `backtest` (the CLI module, importable)

- **`run_backtest(backtest, out_dir, *, source=None) -> BacktestRun`**: runs the backtest and writes the four files. `BacktestRun` has `result`, `run_info` (the `run.json` content), `report` (the `statistics.txt` text) and `paths`.
- The three steps it chains, usable on their own:
  - `build_run_info(backtest, result, *, source=None)`
  - `format_report(result, run_info)`
  - `write_results(result, run_info, report, out_dir, *, price_decimals)`
