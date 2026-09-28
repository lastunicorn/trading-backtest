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
   └──────────────────── Backtest.run() → BacktestResult(trades, statistics) ─────────────────────┘
                                 │
   run_backtest(): provenance (git, time) + report + 4 files in the output directory
```

The central idea: **a strategy only decides where to enter.** It returns open positions: entry time and price, side, stop-loss, take-profit, and optionally a time to be flat by. The framework decides how each one ended, subtracts costs, and computes statistics. So the exit logic, the part most likely to hide bugs, is written and tested once, and every strategy is judged by the same rules.

The code is split in three layers:

| Layer | Package | Does |
|---|---|---|
| domain | `domain/pandas_approach/`, `domain/broker_clock.py`, `domain/sample_size.py`, `domain/symbol.py` | the concepts and all the calculations; no file access, no clock, no git |
| application | `application/` | loads data from files, records provenance, writes results |
| strategies | `strategies/` | concrete `TradingStrategy` subclasses and the registry the CLI uses |

`backtest.py` at the repo root is the command-line entry point.

Everything is pandas-based. Before running anything, activate the repo's virtual environment:

```bash
source .venv/bin/activate
```

---

## How a backtest decides things

Every backtest runs under these rules. Two of them are settings, so pick those deliberately for each strategy (see [Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity)).

**Prices are bid.** The bars hold bid OHLC. Stop-loss and take-profit hits are checked against those prices.

**A hit fills at the level itself.** A long hits TP when a bar's high reaches it and SL when its low does; a short mirrors that. Touching the level counts. The fill is the level even when a bar *gaps* past it, which flatters stop-loss fills after gaps.

**Where checking starts (`PositionResolveDelay`, a setting).**
- `NEXT_BAR` (default) skips the entry bar. Use it when the entry is at a price *inside* the bar, like a level being re-crossed: the bar's high and low may have happened before the fill.
- `ENTRY_BAR` checks the entry bar too. Use it when the entry is at the bar's *open*: everything in that bar then happened after the fill.

**A bar touching both SL and TP is ambiguous (`AmbiguityPolicy`, a setting).** OHLC can't say which came first.
- `EXCLUDE` (default, the research convention) records it as `ambiguous` with no P&L. It is counted, but excluded from every profit figure.
- `ASSUME_SL` settles it as a stop-loss (v28's rule). `ASSUME_TP` settles it as a take-profit.

**The time stop (`exit_dt`).** `exit_dt` is the moment the position must be flat. Bars opening *before* it are traded. If neither level is hit, the position closes as `manual-close` at the close of the last such bar, with `close_dt = exit_dt`.

**End of data.** If the bars run out before a hit or the time stop, the position closes as `end-of-data` at the last bar's close.

**Costs are always subtracted.** Every P&L figure is net of the cost model. `FixedCost` charges a flat amount per trade (default 1.7 pips). `SpreadCost` charges the spread of the bar where the trade crosses to the ask: entry for a long, exit for a short.

**A win means net pips > 0 after costs.** That is not the same as `take-profit-hit`: a take-profit smaller than the cost is still a loss. The report shows both views, as outcome counts and as the win/loss split.

**Results are reported per split.** Calendar days are sorted and cut 60 / 20 / 20 into discovery / validation / test, never shuffled. Each trade belongs to the split of the day it opens. A result is only worth trusting if it holds in all three splits; the report ends with a yes/no line for that.

**Look-ahead is the strategy's job.** `generate_positions` receives the whole history. A signal on bar *i* must only use bars up to *i*.

---

## Checklist and common mistakes

Before trusting a result:

- [ ] **No look-ahead.** Each entry uses only bars up to its own.
- [ ] **The right `resolve_from`** for how the strategy enters ([Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity)).
- [ ] **Costs included.** Never analyse `gross_pips` as if it were the result.
- [ ] **All three splits positive.** One good split is noise. Parameters were chosen on discovery only.
- [ ] **Enough trades per split** for the numbers to mean something.
- [ ] **`excluded_ambiguous` is small.** If not, compare `"ambiguity": "assume-sl"` against `"assume-tp"`.
- [ ] **`run.json` kept with the results**, and the working tree committed (`"dirty": false`).

Common mistakes:

| Symptom | Cause |
|---|---|
| `ERROR: … windows are broker-server times; the data is on UTC` | a broker-clock strategy on Dukascopy data; convert the data to the broker clock with `shift_timezone`, or use MT5 data |
| `ERROR: SpreadCost needs a 'spread' column` | `"spread_cost": true` on the clean CSV, which has no spread; use `cost_pips`, or MT5/Dukascopy data |
| `ERROR: backtest.json: unknown key(s) …` | a misspelt config key; the message lists the allowed ones |
| `ValueError: long position needs sl < open_price < tp` | the strategy built a position with levels on the wrong side; skip such signals |
| `'datetime' must be strictly increasing` | the frame needs `clean_frame` before `HistoricalData` |
| far fewer trades than expected | a fixture or real bar touching a level counts as a hit/break; check the ≥ / ≤ edges |
| results with times 7 hours off | the data was treated as New York time; the broker clock is New York + 7h (`BROKER_SERVER_TZ`) |
| numbers look wrong on a finer `timeframe` | resampling only coarsens: asking for `1m` from an M5 file returns M5 bars labelled 1m |

---

## Further reading

- [Running a backtest](running-a-backtest.md): every `backtest.py` config key, running from Python (custom parameters, sweeps), choosing `resolve_from` and `ambiguity`, data sources and their clocks. **Start here.**
- [Reading the backtest results](reading-the-backtest-results.md): the four files a run writes, every statistic and every column.
- [Writing a new strategy](writing-a-strategy.md): the strategy contract, a worked example, registering it for the CLI, parameter variants, tests.
- [API reference](api-reference.md): every public name, module by module.
- The strategies:
  - [Narrow Asia London Fade](strategy-narrow-asia-fade.md) (`narrow_asia_fade`): the frozen v28 strategy.
  - [RSI Divergence](strategy-rsi-divergence.md) (`rsi_divergence`): regular RSI divergences on M15.
