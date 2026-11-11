# Backtest Framework

A reusable way to backtest any trading strategy on the same historical bars and under the same rules, instead of each research script re-implementing stop-loss/take-profit handling, costs and statistics.

## Contents

- [How it works](#how-it-works)
- [How a backtest decides things](#how-a-backtest-decides-things)
- [Checklist and common mistakes](#checklist-and-common-mistakes)
- [Further reading](#further-reading)

---

## How it works

A backtest runs **one strategy** over **one set of historical bars** under **one set of simulation rules**, and reports how the trades performed:

```
HistoricalData ──► TradingStrategy.generate_positions() ──► open Positions (entry, SL, TP, optional time stop)
                                                              │
                          Backtest._simulate() ◄──────────────┘  decides how each position closed
                                 │
   positions_to_frame ─► CostModel.cost_pips ─► trade_results ─► assign_splits ─► statistics_by_split
   └──────── Backtest.run() → BacktestResult(what ran, trades, statistics, verdict) ──────────────┘
                                 │
   run_backtest(): provenance (git, time) ─► write_results(): report + 4 files in the output directory
```

The central idea: **a strategy only decides where to enter.** It returns open positions: entry time and price, side, stop-loss, take-profit, and optionally a time to be flat by. The framework decides how each one ended, subtracts costs, and computes statistics. So the exit logic, the part most likely to hide bugs, is written and tested once, and every strategy is judged by the same rules.

The framework follows the repo's [architecture](../architecture.md). Each component has this part in a backtest:

| Component | Where | Does in a backtest |
|---|---|---|
| entry script | `backtest.py` | the command line; `run_backtest()` runs the backtest, gathers the provenance (git commit, time) and has the result files written |
| application | `application/` | validates the config (`load_backtest_config`) and loads the historical data (`load_historical_data_use_case.load_source`) |
| ports | `ports/` | read the config file, the MT5 and Dukascopy exports, the clock and git; format and write the result files (`backtest_result_access`) |
| domain | `domain/backtesting/`, `domain/market_data/` | the concepts and all the calculations; no file access, no clock, no git |
| strategies | `strategies/` | concrete `TradingStrategy` subclasses and the registry the config's `strategy.name` looks up |

Everything is pandas-based. Before running anything, activate the repo's virtual environment:

```bash
source .venv/bin/activate
```

---

## How a backtest decides things

Every backtest runs under these rules. One of them is a setting (the config's `simulation.ambiguity`), so pick it deliberately for each strategy (see [Choosing `ambiguity`](running-a-backtest.md#3-choosing-ambiguity)).

**Prices are bid.** The bars hold bid OHLC. Stop-loss and take-profit hits are checked against those prices.

**A hit fills at the level itself.** A long hits TP when a bar's high reaches it and SL when its low does; a short mirrors that. Touching the level counts. The fill is the level even when a bar *gaps* past it, which flatters stop-loss fills after gaps.

**Where checking starts (each position's `entry_fill`, set by the strategy).**
- `EntryFill.AT_LEVEL` (default) skips the entry bar. It is for an entry at a price *inside* the bar, like a level being re-crossed: the bar's high and low may have happened before the fill.
- `EntryFill.AT_OPEN` checks the entry bar too. It is for an entry at the bar's *open*: everything in that bar then happened after the fill.

It is a fact about how the strategy enters, not a choice made per run, so the strategy sets it on every `Position` it emits (`positions.csv` has it as the `entry_fill` column).

**A bar touching both SL and TP is ambiguous (`AmbiguityPolicy`, a setting).** OHLC can't say which came first.
- `EXCLUDE` (default, the research convention) records it as `ambiguous` with no P&L. It is counted, but excluded from every profit figure.
- `ASSUME_SL` settles it as a stop-loss (`narrow_asia_fade`'s rule). `ASSUME_TP` settles it as a take-profit.

**The time stop (`exit_dt`).** `exit_dt` is the moment the position must be flat. Bars opening *before* it are traded. If neither level is hit, the position closes as `manual-close` at the close of the last such bar, with `close_dt = exit_dt`.

**End of data.** If the bars run out before a hit or the time stop, the position closes as `end-of-data` at the last bar's close.

**Costs are always subtracted.** Every P&L figure is net of the cost model. `FixedCost` charges a flat amount per trade (default 1.7 pips). `SpreadCost` charges the spread of the bar where the trade crosses to the ask: entry for a long, exit for a short. A config picks between them with `simulation.cost.spread`, and `simulation.cost.commission_pips` is the flat amount; a config without `simulation.cost` charges nothing.

**A win means net pips > 0 after costs.** That is not the same as `take-profit-hit`: a take-profit smaller than the cost is still a loss. The report shows both views, as outcome counts and as the win/loss split.

**Results can be reported per split.** With `"splits": "dvt"`, calendar days are sorted and cut 60 / 20 / 20 into discovery / validation / test, never shuffled. Each trade belongs to the split of the day it opens. A result is only worth trusting if it holds in all three splits; the report ends with a yes/no line for that. `"monthly"` and `"yearly"` group trades by calendar period instead, to show whether the edge is spread over time or comes from a few periods. The default, `"none"`, reports all trades only.

**Look-ahead is the strategy's job.** `generate_positions` receives the whole history. A signal on bar *i* must only use bars up to *i*.

---

## Checklist and common mistakes

Before trusting a result:

- [ ] **No look-ahead.** Each entry uses only bars up to its own.
- [ ] **The right `entry_fill`** on the strategy's positions for how it enters ([Where checking starts](#how-a-backtest-decides-things)).
- [ ] **Costs included.** Never analyse `gross_pips` as if it were the result.
- [ ] **All three splits positive** (run with `"splits": "dvt"`). One good split is noise. Parameters were chosen on discovery only.
- [ ] **Enough trades per split** for the numbers to mean something.
- [ ] **`excluded_ambiguous` is small.** If not, compare `simulation.ambiguity` `"assume-sl"` against `"assume-tp"`.
- [ ] **`run.json` kept with the results**, and the working tree committed (`"dirty": false`).

Common mistakes:

| Symptom | Cause |
|---|---|
| `ERROR: … windows are broker-server times; the data is on UTC` | a broker-clock strategy on data that isn't on the broker clock: Dukascopy, histdata (`"histdata"`), or a config that left `data_source.timezone` at its `"UTC"` default. If the files really are broker-server time, set `"timezone": "broker"`; otherwise convert them with `shift_timezone` or use broker MT5 exports |
| `ERROR: SpreadCost needs a 'spread' column` | `"simulation": {"cost": {"spread": true}}` on data with no spread, such as histdata.com exports; drop `spread` and set `commission_pips`, or use broker MT5/Dukascopy data |
| `ERROR: backtest.json: unknown key(s) …` | a misspelt config key, or a `simulation` key (`timeframe`, `ambiguity`, `cost`) written at the root; the message lists the allowed ones |
| `ValueError: long position needs sl < open_price < tp` | the strategy built a position with levels on the wrong side; skip such signals |
| `'datetime' must be strictly increasing` | the frame needs `clean_frame` before `HistoricalData` |
| far fewer trades than expected | a fixture or real bar touching a level counts as a hit/break; check the ≥ / ≤ edges |
| results with times 7 hours off | `data_source.timezone` doesn't match the files: the broker clock is New York + 7h (`"broker"`), histdata is `"histdata"` (New York's clock, on the EU daylight-saving dates from 2019; not checked) |
| histdata results with a few weeks a year 1 hour off (mid-March, late October) | `data_source.timezone` is `"America/New_York"` for histdata: use `"histdata"`, which follows the EU daylight-saving dates the files do from 2019 |
| `ERROR: … "simulation.timeframe" … is not a whole multiple of the source's "data_source.timeframe"` | resampling only coarsens; test on a multiple of the source's bar size, or fix `data_source.timeframe` if it misstates the source |
| numbers look wrong on a finer `simulation.timeframe` | `data_source.timeframe` understates the source (e.g. left at the `1m` default for an M5 file written by `read_csv.py --timeframe 5m --output`), so the check passed; asking for `1m` from an M5 file returns M5 bars labelled 1m |

---

## Further reading

- [Running a backtest](running-a-backtest.md): the `backtest.py` command, running from Python (custom parameters, sweeps), choosing `ambiguity`, data sources and their clocks. **Start here.**
- [The backtest config file](backtest-config.md): the JSON config's structure, every key and its default, strategy parameter overrides, validation.
- [Reading the backtest results](reading-the-backtest-results.md): the four files a run writes, every statistic and every column.
- [Writing a new strategy](writing-a-strategy.md): the strategy contract, a worked example, registering it for the CLI, parameter variants, tests.
- [API reference](api-reference.md): every public name, module by module.
- [The strategies](../strategies/README.md): one folder per registered strategy in `doc/strategies/`: its implementation (rules, parameters, how to backtest it) and, for some, its original rules.
