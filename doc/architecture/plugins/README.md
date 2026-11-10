# Plugins: Strategies

A strategy is a plugin: it decides where to **enter** and returns open positions; the backtest decides how each one closed ([domain/backtest.md](../domain/backtest.md#4-backtest-and-the-exit-rules)). Strategies are found by name in a registry, built from a config's parameters and recorded in `run.json`. Adding one touches nothing outside the plugins (plus its tests and documentation page). Types and rules are in [conventions.md](../conventions.md).

Each strategy has its own page here. The trading rules of each strategy are also written for traders in `doc/strategies/<name>/<name>-implementation.md`; these pages are the contract a re-implementation must meet.

| Page | Strategy | Registered as |
|---|---|---|
| [narrow-asia-fade.md](narrow-asia-fade.md) | NarrowAsiaFade | `narrow_asia_fade` |
| [opening-range-strategy.md](opening-range-strategy.md) | OpeningRangeStrategy, the ORB strategies' shared base | not registered |
| [orb-break-entry.md](orb-break-entry.md) | OrbBreakEntry | `orb_break_entry` |
| [orb-retest-entry.md](orb-retest-entry.md) | OrbRetestEntry | `orb_retest_entry` |
| [rsi-divergence.md](rsi-divergence.md) | RsiDivergence | `rsi_divergence` |
| [session-breakout.md](session-breakout.md) | SessionBreakout | `session_breakout` |

---

## The plugin contract: TradingStrategy

*Python: `domain/pandas_approach/trading_strategy.py`.* An abstract base every strategy implements. A strategy is an **immutable value**: its parameters are fixed at construction, and two runs with the same parameters on the same data return the same positions.

| Action | Returns | Description |
|---|---|---|
| `name` | `String` | A label for reports; the class name unless overridden. |
| `parameters()` | `Map<String, Any>` | The settings that define this run: every parameter, in declaration order, with its value (a `TradingSession` stays an object). |
| `split_days(data: HistoricalData)` | `List<Date>` | The days the discovery / validation / test split is cut over. Default: every date with a bar, in order. Override when the strategy trades only some days, so the boundaries fall between tradable days. |
| `generate_positions(data: HistoricalData)` | `List<Position>` | **Abstract.** Every entry the strategy takes over `data`, as open positions ([Position](../domain/backtest.md#2-position)): `open_dt`, `open_price`, `side`, `sl`, `tp`, `entry_fill`, optionally `exit_dt` and `tag`. |

Obligations of `generate_positions`:

- **No look-ahead.** It sees the whole history, so a signal decided on bar `i` may use bars up to `i` only. This is the strategy's responsibility; the framework cannot check it.
- **Open positions only**, each opening at or after the first bar (the backtest refuses anything else).
- **Choose `entry_fill` honestly:** `AT_LEVEL` for an order filled at a level inside its bar, `AT_OPEN` for an entry at a bar's open.
- **Set `exit_dt`** to the moment the position must be flat, when the strategy has a time stop.
- **Fail loudly** on data it can't trade correctly (wrong clock, wrong bar size) instead of trading the wrong hours.

Construction validates the parameters; an invalid one is the error `INVALID_PARAMETER` with a message naming it. The order of positions in the list doesn't matter: the backtest sorts trades by `open_dt` (stable).

---

## Registry and parameters

### The registry, `STRATEGIES: Map<String, StrategyConstructor>`

*Python: `strategies/__init__.py`.* Maps the name a config's `strategy.name` accepts to the strategy it builds. A strategy outside the registry still works from code, just not from a config.

| Name | Strategy | Page |
|---|---|---|
| `narrow_asia_fade` | NarrowAsiaFade | [narrow-asia-fade.md](narrow-asia-fade.md) |
| `orb_break_entry` | OrbBreakEntry | [orb-break-entry.md](orb-break-entry.md) |
| `orb_retest_entry` | OrbRetestEntry | [orb-retest-entry.md](orb-retest-entry.md) |
| `rsi_divergence` | RsiDivergence | [rsi-divergence.md](rsi-divergence.md) |
| `session_breakout` | SessionBreakout | [session-breakout.md](session-breakout.md) |

### Parameters

A strategy's parameters are its constructor arguments, each with a type and a default. A config's `strategy.parameters` overrides any subset; the rest keep their defaults. The types a config can set are `Integer`, `Float`, `Boolean`, `String`, `LocalTime`, `ZonedTime`, `TradingSession` and optional versions of these; how each is written in JSON is in [LoadBacktestConfig](../use-cases/load-backtest-config.md#parameter-conversion). A parameter of any other type can only be set from code.

`LocalTime` and `ZonedTime` are different types on purpose: a `LocalTime` is read on the data's own clock (`"10:00"`), a `ZonedTime` names its zone (`"10:00 broker"`, `"08:00 Europe/London"`), so neither can be written as the other.

### Recording parameters

`run.json` and the report record `parameters()` in the spelling a config reads back where there is one:

| Value | Recorded as |
|---|---|
| `ZonedTime` | `"HH:MM:SS {clock name}"` (`"08:00:00 Europe/London"`, `"10:00:00 broker"`) |
| `LocalTime` | `"HH:MM:SS"` |
| a standard `TradingSession` | its `SESSIONS` name (`"London"`) |
| another `TradingSession` | `{"start_time": …, "end_time": …, "name": …}`, its bounds recorded as `ZonedTime`s |
| `null`, numbers, booleans, strings | as JSON |
