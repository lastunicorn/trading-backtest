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

```json
{
	"strategy": "narrow_asia_fade",
	"data": {
		"source": "../../output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv",
		"format": "clean-csv",
		"symbol": "EURUSD",
		"timeframe": "5m",
		"timezone": "broker"
	},
	"out": "../../output/backtest_narrow_asia_fade",
	"ambiguity": "assume-sl",
	"resolve_from": "next-bar"
}
```

**Relative paths (`data.source`, `out`) are resolved against the config file's folder**, not the directory you run from, so a config gives the same run wherever it is launched. Ready-made configs live in `backtests/<name>/backtest.json`.

| Key | Required | Default | Meaning |
|---|---|---|---|
| `strategy` | yes | – | A key of `strategies.STRATEGIES`, e.g. `"narrow_asia_fade"`, `"rsi_divergence"`, `"session_breakout"`. |
| `data` | yes | – | The bars as they are on disk: an object with the `data.*` keys below. |
| `data.source` | yes | – | A file or a folder of files in `data.format`. |
| `data.format` | yes | – | How to read `data.source`:<br>`"metatrader"`: MT4/MT5 exports, a folder of them or one file.<br>`"dukascopy"`: Dukascopy bid/ask M1 pairs, a folder of them (searched recursively, so the whole export folder or one year of it) or either file of one pair.<br>`"clean-csv"`: the research pipeline's clean CSV (v24 output). |
| `data.symbol` | yes | – | Ticker of the source data, for pip size and price precision: `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDCAD`, `USDCHF`, `USDJPY`, `XAUUSD`, `XAGUSD`. |
| `data.timeframe` | no | `"1m"` | Bar size of the source as stored: `"1m"` for raw MT5 exports and Dukascopy, `"5m"` for the pipeline clean CSV. Not read from the files: it is what the root `timeframe` is checked against. |
| `data.timezone` | no | `"UTC"` | The clock the source's timestamps are on: an IANA name (`"UTC"`, `"America/New_York"`, …) or `"broker"` for the MT5 broker-server clock (New York + 7h). It labels the bars and is never inferred from `data.format`: see [Data sources and clocks](#4-data-sources-and-clocks). Nothing is shifted, so a strategy with wall-clock windows must get data on the clock it expects. |
| `out` | yes | – | Output directory. Created if missing; existing result files are **overwritten**. |
| `timeframe` | no | `"5m"` | Bar size to test on: `5m`, `15m`, `1h`, `4h`, `1d`… (`m` minutes, `h` hours, `d` days, `w` weeks, `M` months). The source is resampled to it, so it must be a whole multiple of `data.timeframe` (`15m` from `5m`, not `1m` or `7m` from `5m`); anything else is rejected when the config loads (see [Checklist and common mistakes](README.md#checklist-and-common-mistakes)). |
| `cost_pips` | no | `1.7` | Fixed round-trip cost per trade, in pips (`FixedCost`). |
| `spread_cost` | no | `false` | `true`: charge each trade the bar's spread instead of `cost_pips` (`SpreadCost`). Needs data with a `spread` column: MT5 raw exports or Dukascopy, not the clean CSV. |
| `commission_pips` | no | `0` | With `spread_cost`: a flat commission added per trade. |
| `ambiguity` | no | `"exclude"` | A bar touching both SL and TP: `exclude`, `assume-sl` or `assume-tp`. |
| `resolve_from` | no | `"next-bar"` | First bar SL/TP are checked on: `next-bar` or `entry-bar`. |
| `splits` | no | `true` | `false`: report only "all", without the discovery/validation/test breakdown. |
| `strategy_parameters` | no | `{}` | Overrides for the strategy's own parameters (its dataclass fields, listed on each strategy's page); the rest keep their defaults. Numbers, whole numbers, `true`/`false` and strings as JSON; time-of-day fields as `"HH:MM"` strings. See below. |

A variant of a strategy only needs `strategy_parameters`; the report header and `run.json` record the full parameter set the run used:

```json
{
	"strategy": "narrow_asia_fade",
	"data": {
		"source": "../../output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv",
		"format": "clean-csv",
		"symbol": "EURUSD",
		"timeframe": "5m",
		"timezone": "broker"
	},
	"out": "../../scratch/backtest_narrow_asia_fade_1300",
	"ambiguity": "assume-sl",
	"strategy_parameters": {"study_end": "13:00", "rel_vol_min": 1.8}
}
```

The config is checked before any data is read: an unknown key (a typo such as `"ambigutiy"`), a value of the wrong JSON type, a missing required key, an invalid choice, a `timeframe` that isn't a whole multiple of `data.timeframe`, or a strategy parameter the strategy doesn't have or rejects (e.g. a negative `risk_reward`) prints `ERROR: <file>: …` and exits with code 1, rather than quietly running on a default. The same happens when the data and the strategy don't fit together: a broker-clock strategy on data whose `data.timezone` isn't `"broker"`, an invalid `data.timezone`, a Dukascopy source with a non-UTC `data.timezone`, `spread_cost` without a spread column, a missing source or an incomplete Dukascopy bid/ask pair, or an unknown timeframe or symbol.

More examples, both in `backtests/`:

```json
// backtests/rsi_divergence/backtest.json: M15 bars rebuilt from raw M1 exports; entries are at a bar's open
{
	"strategy": "rsi_divergence",
	"data": {"source": "../../data/eurusd/1min", "format": "metatrader", "symbol": "EURUSD", "timezone": "broker"},
	"out": "../../scratch/backtest_rsi_divergence",
	"timeframe": "15m",
	"resolve_from": "entry-bar"
}

// backtests/rsi_divergence_dukascopy/backtest.json: the same on Dukascopy data, charging the real spread plus a commission
{
	"strategy": "rsi_divergence",
	"data": {"source": "/path/to/ducascopy/eurusd/2025", "format": "dukascopy", "symbol": "EURUSD"},
	"out": "../../scratch/backtest_rsi_duka",
	"timeframe": "15m",
	"resolve_from": "entry-bar",
	"spread_cost": true,
	"commission_pips": 0.2
}
```

(JSON itself has no comments; they are only labels here.)

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
