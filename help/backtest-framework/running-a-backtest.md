# Running a Backtest

A companion to the [framework overview](README.md). The rules every run follows are in [How a backtest decides things](README.md#how-a-backtest-decides-things); what the output files contain is in [Reading the results](reading-the-backtest-results.md). To add a strategy of your own, see [Writing a new strategy](writing-a-strategy.md).

## Contents

1. [From the command line](#1-from-the-command-line)
2. [From Python](#2-from-python)
3. [Choosing `--resolve-from` and `--ambiguity`](#3-choosing---resolve-from-and---ambiguity)
4. [Data sources and clocks](#4-data-sources-and-clocks)

---

## 1. From the command line

```bash
python3 backtest.py --strategy NAME (--source PATH | --dukascopy-years YEAR [YEAR ...]) --out DIR [options]
```

| Parameter | Required | Default | Meaning |
|---|---|---|---|
| `--strategy NAME` | yes | – | A key of `strategies.STRATEGIES`, e.g. `narrow_asia_fade`, `rsi_divergence`. |
| `--source PATH` | one of these two | – | A pipeline clean CSV (recognised by its `datetime` header), a folder of MT5 exports, or one MT5 export. Bars are on the broker-server clock. |
| `--dukascopy-years YEAR …` | one of these two | – | Read Dukascopy bid/ask M1 pairs for these years from the folder set in `ports/ducascopy/config.py`. Bars are in **UTC**. |
| `--out DIR` | yes | – | Output directory. Created if missing; existing result files are **overwritten**. |
| `--timeframe` | no | `5m` | Bar size to test on: `5m`, `15m`, `1h`, `4h`, `1d`… (`m` minutes, `h` hours, `d` days, `w` weeks, `M` months). The source is resampled to it. It must not be finer than the source (see [Checklist and common mistakes](README.md#checklist-and-common-mistakes)). |
| `--symbol` | no | `EURUSD` | Ticker, for pip size and price precision: `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDCAD`, `USDCHF`, `USDJPY`, `XAUUSD`, `XAGUSD`. |
| `--cost-pips` | no | `1.7` | Fixed round-trip cost per trade, in pips (`FixedCost`). |
| `--spread-cost` | no | off | Charge each trade the bar's spread instead of `--cost-pips` (`SpreadCost`). Needs data with a `spread` column: MT5 raw exports or Dukascopy, not the clean CSV. |
| `--commission-pips` | no | `0` | With `--spread-cost`: a flat commission added per trade. |
| `--ambiguity` | no | `exclude` | A bar touching both SL and TP: `exclude`, `assume-sl` or `assume-tp`. |
| `--resolve-from` | no | `next-bar` | First bar SL/TP are checked on: `next-bar` or `entry-bar`. |
| `--no-splits` | no | off | Report only "all", without the discovery/validation/test breakdown. |

If the data and the strategy don't fit together, the CLI prints `ERROR: …` and exits with code 1. Examples: a broker-clock strategy on UTC data, `--spread-cost` without a spread column, a missing Dukascopy year, or an unknown timeframe or symbol.

More examples:

```bash
# RSI divergence on M15 bars rebuilt from raw M1 exports; entries are at a bar's open
python3 backtest.py --strategy rsi_divergence --timeframe 15m --resolve-from entry-bar \
    --source data/eurusd/1min --out scratch/backtest_rsi

# The same on Dukascopy data, charging the real spread plus a commission
python3 backtest.py --strategy rsi_divergence --timeframe 15m --resolve-from entry-bar \
    --dukascopy-years 2024 2025 --spread-cost --commission-pips 0.2 --out scratch/backtest_rsi_duka
```

## 2. From Python

Use this when you need non-default strategy parameters, several runs in a loop, or the numbers without files:

```python
from application.load_historical_data_use_case import load_source
from backtest import run_backtest
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, PositionResolveDelay
from domain.pandas_approach.cost_model import FixedCost
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from strategies.opening_range_breakout import OpeningRangeBreakout

data = load_source("output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv", SampleSize.Parse("5m"), EurUsd())
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

## 3. Choosing `--resolve-from` and `--ambiguity`

| Your entry happens… | `--resolve-from` | Why |
|---|---|---|
| at a level inside a bar (breakout, re-cross, limit or stop order) | `next-bar` | the bar's range may have happened before the fill |
| at a bar's open (signal confirmed on the previous bar) | `entry-bar` | the whole bar happened after the fill |

For `--ambiguity`, keep `exclude` unless you are reproducing a study that used another rule, as v28 used `assume-sl`. Then compare the two. If they differ a lot, your stop and target are close enough together that bar size matters; check the `excluded_ambiguous` count.

## 4. Data sources and clocks

| Source | Loader | Spread in the file | Clock (`data.timezone`) |
|---|---|---|---|
| MT5 exports, `resample_csv.py` output | `load_mt5` | points (tick size) | broker server |
| Pipeline clean CSV (v24 output) | `load_clean_csv` | none | broker server |
| Dukascopy bid/ask pairs | `load_dukascopy` | price units (ask − bid) | UTC |

The loaders convert spread to pips. The **broker-server clock is New York + 7 hours** (GMT+2 in winter, GMT+3 in summer, switching on the US daylight-saving dates), available as `domain.broker_clock.BROKER_SERVER_TZ`. To move a frame between clocks, use `domain.pandas_approach.shift_timezone.shift_timezone`.
