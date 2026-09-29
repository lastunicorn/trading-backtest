# Running a Backtest

A companion to the [framework overview](README.md). The rules every run follows are in [How a backtest decides things](README.md#how-a-backtest-decides-things); what the output files contain is in [Reading the results](reading-the-backtest-results.md). To add a strategy of your own, see [Writing a new strategy](writing-a-strategy.md).

## Contents

1. [From the command line](#1-from-the-command-line)
2. [From Python](#2-from-python)
3. [Choosing `resolve_from` and `ambiguity`](#3-choosing-resolve_from-and-ambiguity)
4. [Data sources and clocks](#4-data-sources-and-clocks)

---

## 1. From the command line

Every setting lives in a JSON config file; the command takes only its path:

```bash
python3 backtest.py backtests/narrow_asia_fade/backtest.json
python3 backtest.py backtests/narrow_asia_fade        # a folder: reads the backtest.json inside it
```

Ready-made configs live in `backtests/<name>/backtest.json`. The file's structure, every key with its default, strategy parameter overrides, validation errors and more examples are in [The backtest config file](backtest-config.md). Note that **relative paths (`data.source`, `out`) are resolved against the config file's folder**, not the directory you run from.

## 2. From Python

Use this for several runs in a loop (parameter sweeps), or the numbers without files:

```python
from application.load_historical_data_use_case import SourceFormat, load_source
from backtest import run_backtest
from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, PositionResolveDelay
from domain.pandas_approach.cost_model import FixedCost
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from strategies.opening_range_breakout import OpeningRangeBreakout

data = load_source("output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv", SourceFormat.CLEAN_CSV,
                   SampleSize.Parse("5m"), EurUsd(), timezone=BROKER_SERVER_TZ)
backtest = Backtest(
    OpeningRangeBreakout(risk_reward=1.5),
    data,
    cost_model=FixedCost(pips=1.7),
    ambiguity_policy=AmbiguityPolicy.EXCLUDE,
    position_resolve_delay=PositionResolveDelay.NEXT_BAR,
)

result = backtest.run()                          # numbers only, nothing written
result.statistics.loc[["all", "test"], ["trades", "win_rate_pct", "total_net_pips", "profit_factor"]]
result.trades[["open_dt", "side", "outcome", "net_pips", "split"]]

run = run_backtest(backtest, "scratch/orb_1_5r", source="clean M5")   # also writes the 4 files
print(run.report)
```

Load the data once and reuse it across runs; `HistoricalData` must not be modified in place.

A parameter sweep:

```python
for rr in (1.0, 1.5, 2.0):
    stats = Backtest(OpeningRangeBreakout(risk_reward=rr), data).run().statistics
    print(rr, stats.loc["discovery", "total_net_pips"], stats.loc["test", "total_net_pips"])
```

**Choose parameters on the discovery split only.** Validation and test are there to confirm a choice, not to make it. That is the repo's methodology.

## 3. Choosing `resolve_from` and `ambiguity`

| Your entry happens… | `resolve_from` | Why |
|---|---|---|
| at a level inside a bar (breakout, re-cross, limit or stop order) | `next-bar` | the bar's range may have happened before the fill |
| at a bar's open (signal confirmed on the previous bar) | `entry-bar` | the whole bar happened after the fill |

For `ambiguity`, keep `exclude` unless you are reproducing a study that used another rule, as v28 used `assume-sl`. Then compare the two. If they differ a lot, your stop and target are close enough together that bar size matters; check the `excluded_ambiguous` count.

## 4. Data sources and clocks

The clock is not part of the format: two MetaTrader exports can be on different clocks. Set `data.timezone` (default `"UTC"`) to the clock of the files you point at:

| Source | `data.format` | Loader | Spread in the file | `data.timezone` |
|---|---|---|---|---|
| this repo's MT5 broker exports (`data/eurusd/1min`), `resample_csv.py` output | `metatrader` | `load_mt5` | points (tick size) | `"broker"` |
| histdata.com MT exports (`DAT_MT_EURUSD_M1_*.csv`) | `metatrader` | `load_mt5` | none | `"America/New_York"` (week opens Sunday 17:00; broker time − 7h, checked against the broker exports) |
| Pipeline clean CSV (v24 output) | `clean-csv` | `load_clean_csv` | none | `"broker"` |
| Dukascopy bid/ask pairs | `dukascopy` | `load_dukascopy` | price units (ask − bid) | `"UTC"`, the only one accepted (the timestamps are epoch milliseconds) |

The loaders convert spread to pips. The **broker-server clock is New York + 7 hours** (GMT+2 in winter, GMT+3 in summer, switching on the US daylight-saving dates), available as `domain.broker_clock.BROKER_SERVER_TZ`. To move a frame between clocks, use `domain.pandas_approach.shift_timezone.shift_timezone`.
