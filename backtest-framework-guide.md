# Backtest Framework — User Guide

## Contents

1. [Overview](#1-overview)
2. [Quick start](#2-quick-start)
3. [How a backtest decides things](#3-how-a-backtest-decides-things)
4. [Writing a new strategy](#4-writing-a-new-strategy)
5. [Running a backtest](#5-running-a-backtest)
6. [Reading the results](#6-reading-the-results)
7. [API reference](#7-api-reference)
8. [Built-in strategies](#8-built-in-strategies)
9. [Checklist and common mistakes](#9-checklist-and-common-mistakes)

---

## 1. Overview

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

## 2. Quick start

Run the frozen v28 strategy on the canonical M5 dataset:

```bash
python3 backtest.py --strategy narrow_asia_fade --ambiguity assume-sl --resolve-from next-bar \
    --source output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv --out output/backtest_narrow_asia_fade
```

It prints the statistics report and writes four files into `--out`. The result reproduces v28 exactly: 207 trades, 72.0% win rate, profit factor 1.37, +257.5 net pips. The last lines of the report:

```
                                  all   discovery  validation        test
-------------------------------------------------------------------------
trades                            207         119          60          28
...
win_rate_pct                    72.0%       71.4%       75.0%       67.9%
total_net_pips                  257.5       163.0        50.7        43.7
profit_factor                    1.37        1.41        1.23        1.53

Net positive in every split (discovery, validation, test): yes
```

The same run from Python:

```python
from application.load_historical_data_use_case import load_source
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from strategies.narrow_asia_fade import NarrowAsiaFade

data = load_source("output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv", SampleSize.Parse("5m"), EurUsd())
result = Backtest(NarrowAsiaFade(), data, ambiguity_policy=AmbiguityPolicy.ASSUME_SL).run()

result.statistics.loc["all", "total_net_pips"]     # 257.45 (the report rounds it to 257.5)
result.trades.head()                                # one row per trade
```

---

## 3. How a backtest decides things

Every backtest runs under these rules. Two of them are settings, so pick those deliberately for each strategy (see [5.3](#53-choosing---resolve-from-and---ambiguity)).

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

## 4. Writing a new strategy

This section builds a complete strategy step by step: a **London opening-range breakout**. The code below was run on the canonical dataset and its tests pass.

### 4.1 The contract

Subclass `TradingStrategy` and implement one method:

```python
def generate_positions(self, data: HistoricalData) -> list[Position]:
```

Return **open** positions: `Position(open_dt, open_price, side, sl, tp, exit_dt=None, tag="")`. Don't close them; the simulator does that.

Optional overrides:

| Method | Default | Override when |
|---|---|---|
| `name` (property) | the class name | you want a different label in reports |
| `parameters()` | the dataclass fields | the strategy isn't a dataclass |
| `split_days(data)` | every calendar day with a bar | the strategy only trades some days and the 60/20/20 cut should use those |

**Write the strategy as a frozen dataclass.** Its fields are then its parameters. They are recorded in `run.json` and printed in the report header, and a variant is just `MyStrategy(field=value)`.

### 4.2 The strategy

Create `strategies/opening_range_breakout.py`:

```python
"""London opening-range breakout -- the worked example from backtest-framework-guide.md."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

import pandas as pd

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Position, Side
from domain.pandas_approach.trading_strategy import TradingStrategy


@dataclass(frozen=True)
class OpeningRangeBreakout(TradingStrategy):
    """Trade the first break of the London opening range (broker-server time).

    The range is the high/low of the bars opening in [range_start, range_end).
    The first later bar reaching past it opens a trade at the broken level:
    long above the high, short below the low. Stop at the opposite side of the
    range, target `risk_reward` x the range, flat by `exit_at`.
    """

    range_start: time = time(10, 0)
    range_end: time = time(11, 0)
    exit_at: time = time(18, 0)
    risk_reward: float = 1.0
    max_range_pips: float = 30.0

    def generate_positions(self, data: HistoricalData) -> list[Position]:
        positions = []
        for day, bars in data.data.groupby(data.data["datetime"].dt.date):
            clock = bars["datetime"].dt.time
            opening = bars[(clock >= self.range_start) & (clock < self.range_end)]
            later = bars[(clock >= self.range_end) & (clock < self.exit_at)]
            if opening.empty or later.empty:
                continue

            high, low = opening["high"].max(), opening["low"].min()
            if data.symbol.to_pips(high - low) > self.max_range_pips:
                continue

            broke_up = later["high"] >= high
            broke_down = later["low"] <= low
            broke = broke_up | broke_down
            if not broke.any():
                continue

            first = broke.idxmax()                  # label of the first breaking bar
            if broke_up[first] and broke_down[first]:
                continue                            # both sides in one bar: unknowable, skip

            width = high - low
            if broke_up[first]:
                side, entry, sl, tp = Side.LONG, high, low, high + self.risk_reward * width
            else:
                side, entry, sl, tp = Side.SHORT, low, high, low - self.risk_reward * width

            positions.append(Position(
                open_dt=bars.at[first, "datetime"],
                open_price=entry,
                side=side,
                sl=sl,
                tp=tp,
                exit_dt=pd.Timestamp(datetime.combine(day, self.exit_at)),
                tag="break-high" if side == Side.LONG else "break-low",
            ))
        return positions
```

Things this example gets right, and every strategy should:

- **No look-ahead.** The opening range uses only bars before `range_end`, and the entry is the first bar that breaks it.
- **Entry at the level.** The fill is inside the breaking bar, so this strategy should run with `--resolve-from next-bar` (the default).
- **Valid levels.** `Position` checks that `sl < open_price < tp` for a long and the reverse for a short, and raises otherwise. Skip a signal whose levels would be invalid rather than letting it raise.
- **A time stop.** `exit_dt` flattens the trade at 18:00 instead of leaving it open for days.
- **A `tag`.** It becomes a column in `positions.csv` that you can group results by later.
- **Session times use the data's clock.** Here that is broker-server time. If your windows only make sense on one clock, check `data.timezone` and raise on any other, as `NarrowAsiaFade` does:

  ```python
  from domain.broker_clock import BROKER_SERVER_TZ
  
  if data.timezone != BROKER_SERVER_TZ:
      raise ValueError(f"windows are broker-server times; the data is on {data.timezone}")
  ```

For speed on large datasets, prefer NumPy arrays over row-by-row pandas; `strategies/narrow_asia_fade.py` shows the pattern. The version above favours readability and still takes about 2 seconds on 485k M5 bars.

### 4.3 Register it for the CLI

Add it to `strategies/__init__.py`:

```python
from strategies.opening_range_breakout import OpeningRangeBreakout

STRATEGIES: dict[str, type[TradingStrategy]] = {
    "narrow_asia_fade": NarrowAsiaFade,
    "rsi_divergence": RsiDivergence,
    "opening_range_breakout": OpeningRangeBreakout,
}
```

The key is the name `--strategy` accepts. The CLI builds the class **with its default parameters**. To run other values, see [5.2](#52-from-python) or add a variant (next section).

### 4.4 Variants with different parameters

The CLI has no per-parameter flags; strategy settings belong to the strategy definition. To run a variant from the command line, register a subclass that changes the defaults:

```python
@dataclass(frozen=True)
class OpeningRangeBreakout2R(OpeningRangeBreakout):
    risk_reward: float = 2.0

STRATEGIES["opening_range_breakout_2r"] = OpeningRangeBreakout2R
```

From Python, just pass the values: `OpeningRangeBreakout(risk_reward=2.0, exit_at=time(16, 0))`.

### 4.5 Test it

Tests go in `tests/strategies/<module>/`, one file per method, with an `__init__.py` in each directory. Build a small synthetic day where you control every bar:

```python
"""Tests for `strategies.opening_range_breakout.OpeningRangeBreakout.generate_positions`."""

import pandas as pd
import pytest

from domain.pandas_approach.historical_data import HistoricalData
from domain.pandas_approach.position import Side
from domain.sample_size import SampleSize
from domain.symbol import EurUsd
from strategies.opening_range_breakout import OpeningRangeBreakout

RANGE_BAR = (1.1000, 1.1005, 1.0995, 1.1000)  # sets the opening range: 1.0995-1.1005
QUIET = (1.1000, 1.1004, 1.0996, 1.1000)      # stays strictly inside it
BREAK_UP = (1.1003, 1.1008, 1.1002, 1.1007)


def _data(overrides: dict[str, tuple]) -> HistoricalData:
    """One Monday of M5 bars from 10:00 to 17:55: quiet, with the 10:30 bar setting the
    opening range, plus `overrides` ("HH:MM" -> (open, high, low, close))."""
    stamps = pd.date_range("2026-01-05 10:00", "2026-01-05 17:55", freq="5min")
    bars = {"10:30": RANGE_BAR, **overrides}
    rows = [bars.get(t.strftime("%H:%M"), QUIET) for t in stamps]
    frame = pd.DataFrame(rows, columns=["open", "high", "low", "close"])
    frame.insert(0, "datetime", stamps)
    return HistoricalData(frame, SampleSize.Parse("5m"), EurUsd())


def test_break_above_the_opening_range_is_a_long_at_its_high() -> None:
    data = _data({"11:20": BREAK_UP})

    [position] = OpeningRangeBreakout().generate_positions(data)

    assert position.side == Side.LONG
    assert position.open_dt == pd.Timestamp("2026-01-05 11:20")
    assert position.open_price == 1.1005
    assert position.sl == 1.0995
    assert position.tp == pytest.approx(1.1015)
    assert position.exit_dt == pd.Timestamp("2026-01-05 18:00")


def test_no_break_no_trade() -> None:
    assert OpeningRangeBreakout().generate_positions(_data({})) == []
```

**Watch out for touching counting as a break.** Default bars that sit exactly *on* a level count as a break. The fixture above keeps quiet bars strictly inside the range for that reason. If a "nothing happens" test passes, make sure it passes because nothing broke, not because every bar was skipped as ambiguous.

Run everything with `pytest` from the repo root.

### 4.6 Run it

```bash
python3 backtest.py --strategy opening_range_breakout \
    --source output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv --out scratch/backtest_orb
```

For this example that gives 1,449 trades, a 49.3% win rate and profit factor 0.82: not profitable, but a working end-to-end run.

---

## 5. Running a backtest

### 5.1 From the command line

```bash
python3 backtest.py --strategy NAME (--source PATH | --dukascopy-years YEAR [YEAR ...]) --out DIR [options]
```

| Parameter | Required | Default | Meaning |
|---|---|---|---|
| `--strategy NAME` | yes | – | A key of `strategies.STRATEGIES`, e.g. `narrow_asia_fade`, `rsi_divergence`. |
| `--source PATH` | one of these two | – | A pipeline clean CSV (recognised by its `datetime` header), a folder of MT5 exports, or one MT5 export. Bars are on the broker-server clock. |
| `--dukascopy-years YEAR …` | one of these two | – | Read Dukascopy bid/ask M1 pairs for these years from the folder set in `ports/ducascopy/config.py`. Bars are in **UTC**. |
| `--out DIR` | yes | – | Output directory. Created if missing; existing result files are **overwritten**. |
| `--timeframe` | no | `5m` | Bar size to test on: `5m`, `15m`, `1h`, `4h`, `1d`… (`m` minutes, `h` hours, `d` days, `w` weeks, `M` months). The source is resampled to it. It must not be finer than the source (see §9). |
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

### 5.2 From Python

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

### 5.3 Choosing `--resolve-from` and `--ambiguity`

| Your entry happens… | `--resolve-from` | Why |
|---|---|---|
| at a level inside a bar (breakout, re-cross, limit or stop order) | `next-bar` | the bar's range may have happened before the fill |
| at a bar's open (signal confirmed on the previous bar) | `entry-bar` | the whole bar happened after the fill |

For `--ambiguity`, keep `exclude` unless you are reproducing a study that used another rule, as v28 used `assume-sl`. Then compare the two. If they differ a lot, your stop and target are close enough together that bar size matters; check the `excluded_ambiguous` count.

### 5.4 Data sources and clocks

| Source | Loader | Spread in the file | Clock (`data.timezone`) |
|---|---|---|---|
| MT5 exports, `resample_csv.py` output | `load_mt5` | points (tick size) | broker server |
| Pipeline clean CSV (v24 output) | `load_clean_csv` | none | broker server |
| Dukascopy bid/ask pairs | `load_dukascopy` | price units (ask − bid) | UTC |

The loaders convert spread to pips. The **broker-server clock is New York + 7 hours** (GMT+2 in winter, GMT+3 in summer, switching on the US daylight-saving dates), available as `domain.broker_clock.BROKER_SERVER_TZ`. To move a frame between clocks, use `domain.pandas_approach.shift_timezone.shift_timezone`.

---

## 6. Reading the results

`--out` (or `run_backtest`) produces four files.

### `statistics.txt` — read this first

A header with the strategy, its parameters, the data, the source, the cost model, the simulation settings, the creation time and the git commit. Below it is the statistics table, one column per split, and a final line: *Net positive in every split: yes/no*.

### `statistics.csv`

The same numbers, one row per split (`all`, `discovery`, `validation`, `test`), for comparing runs. The metrics, which are also the keys of `compute_statistics()`:

| Metric | Meaning |
|---|---|
| `trades` | positions opened |
| `outcome_open`, `outcome_stop-loss-hit`, `outcome_take-profit-hit`, `outcome_manual-close`, `outcome_end-of-data`, `outcome_ambiguous` | count per outcome |
| `excluded_ambiguous` | ambiguous trades left out of every P&L figure |
| `resolved` | trades with a P&L, i.e. `trades` minus ambiguous |
| `wins` / `losses` | `net_pips > 0` / `net_pips ≤ 0` |
| `win_rate_pct` | wins ÷ resolved × 100 |
| `total_gross_pips`, `total_cost_pips`, `total_net_pips` | sums before costs, of costs, and after costs |
| `avg_net_pips`, `median_net_pips` | per resolved trade |
| `avg_win_pips`, `avg_loss_pips` | average net result of wins / of losses |
| `profit_factor` | gross profit ÷ gross loss, net of costs (`inf` with no losses, `n/a` with no P&L) |
| `expectancy_r` | average `net_r`: result per trade in units of its risk |
| `max_drawdown_pips` | largest peak-to-trough drop of cumulative net pips, trades in entry order |
| `max_consecutive_losses` | longest losing streak |
| `avg_duration_min` | average minutes from entry to close |

A split with no trades shows 0 counts and `n/a` figures.

### `positions.csv`

One row per trade, sorted by entry time:

| Column | Meaning |
|---|---|
| `open_dt`, `side`, `open_price`, `sl`, `tp`, `exit_dt` | what the strategy asked for |
| `close_dt`, `close_price`, `outcome` | what the simulator decided (`close_price` is empty for `ambiguous`) |
| `tag` | the strategy's free-text label |
| `gross_pips`, `cost_pips`, `net_pips` | result before costs, the cost, result after costs |
| `risk_pips`, `net_r` | entry-to-stop distance, and net pips ÷ risk |
| `duration_min` | minutes from `open_dt` to `close_dt` |
| `split` | `discovery`, `validation` or `test` (absent with `--no-splits`) |

`close_dt` is the open time of the bar where SL/TP was hit (OHLC can't say when inside the bar). For a time stop it is `exit_dt` itself.

### `run.json`

Provenance: strategy name, class and parameters; data symbol, timeframe, clock, first/last bar and bar count; cost model, ambiguity and resolve-from settings; trade count; git commit and whether the working tree had uncommitted changes; creation time; source. Keep it with the results, so any number can be traced back to exactly what produced it.

---

## 7. API reference

Only the public names are listed. Everything below `domain/` performs no I/O.

### 7.1 Data

#### `domain.pandas_approach.historical_data`

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

#### `domain.sample_size`

**`SampleSize(amount, unit)`**: a bar size. `SampleSize.Parse("15m")` builds one: `m` minutes, `h` hours, `d` days, `w` weeks, `M` months (case-sensitive). `str(size)` gives `"15m"` back, and `size.to_pandas_rule()` gives the pandas resample rule (`"15min"`).

#### `domain.symbol`

**`Symbol`**: an instrument's constants: `ticker`, `pip_size`, `tick_size`, `to_pips(price_diff)`, `price_decimals`. Concrete classes: `EurUsd()`, `GbpUsd()`, `UsdJpy()`, `XauUsd()`, …; `by_ticker("EURUSD")` looks one up.

#### `domain.broker_clock`

| Name | Meaning |
|---|---|
| `BROKER_SERVER_TZ` | the MT5 server clock, New York + 7h |
| `ShiftedZone(base, shift, name)` | a `tzinfo`: `base`'s wall clock moved by `shift` |
| `timezone_by_name(name)` | `"broker"` → `BROKER_SERVER_TZ`, otherwise `ZoneInfo(name)` |

pandas rejects custom `tzinfo` objects, so don't pass `BROKER_SERVER_TZ` to `tz_localize`; use `shift_timezone`.

#### `domain.pandas_approach.shift_timezone`

**`shift_timezone(frame, to_tz, *, from_tz=BROKER_SERVER_TZ)`**: returns a copy of `frame` with `datetime` re-expressed from `from_tz` to `to_tz`, still naive.

### 7.2 Positions

#### `domain.pandas_approach.side`

**`Side`**: `LONG` (`"long"`), `SHORT` (`"short"`).

#### `domain.pandas_approach.position`

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

### 7.3 Strategies

#### `domain.pandas_approach.trading_strategy`

**`TradingStrategy`** (abstract): see [4.1](#41-the-contract).

| Member | Required | Default |
|---|---|---|
| `generate_positions(data) -> list[Position]` | yes | – |
| `name` (property) | no | class name |
| `parameters() -> dict` | no | dataclass fields, else `{}` |
| `split_days(data) -> Iterable[date]` | no | every calendar day with a bar |

#### `strategies`

**`STRATEGIES`**: `dict[str, type[TradingStrategy]]`, the names `backtest.py --strategy` accepts.

### 7.4 Costs, results, the backtest

#### `domain.pandas_approach.cost_model`

**`CostModel`** (abstract): `cost_pips(trades, data) -> pd.Series`, one round-trip cost in pips per row of a positions frame, aligned to its index. Subclass it to model other frictions.

| Class | Parameters | Charges |
|---|---|---|
| `FixedCost(pips=1.7)` | `pips ≥ 0` | the same cost for every trade |
| `SpreadCost(commission_pips=0.0)` | `commission_pips ≥ 0` | the `spread` of the entry bar (long) or exit bar (short), plus the commission. Raises if the data has no `spread` column or a trade falls on a bar without one. |

#### `domain.pandas_approach.trade_results`

**`trade_results(trades, symbol, cost_pips) -> pd.DataFrame`**: a copy of a positions frame with `RESULT_COLUMNS` appended: `gross_pips, cost_pips, net_pips, risk_pips, net_r, duration_min`. Trades without a close price (ambiguous or open) get NaN P&L.

#### `domain.pandas_approach.splits`

- **`Split`**: `DISCOVERY`, `VALIDATION`, `TEST`.
- **`split_dates(dates, *, discovery=0.60, validation=0.20) -> dict[date, Split]`**: sorts the distinct dates and cuts them chronologically. The boundaries are identical to the research scripts' `split_dates`.
- **`assign_splits(open_dts, by_date) -> pd.Series`**: the split name of each trade from the date it opens on. Raises if a date isn't covered.

#### `domain.pandas_approach.statistics`

- **`compute_statistics(trades) -> dict`**: every metric in [section 6](#statisticscsv), in report order.
- **`statistics_by_split(trades) -> pd.DataFrame`**: one row for `all`, then one per split if the frame has a `split` column.
- **`max_drawdown(net_pips)`**, **`max_consecutive_losses(net_pips)`**: the two building blocks, usable on any sequence.

#### `domain.pandas_approach.backtest`

**`Backtest(strategy, data, cost_model=FixedCost(), ambiguity_policy=AmbiguityPolicy.EXCLUDE, position_resolve_delay=PositionResolveDelay.NEXT_BAR, splits=True)`**: one strategy, one dataset, one set of rules.

- `run() -> BacktestResult`: a pure calculation, with no files, clock or git. It closes every position the strategy returned under the rules in [section 3](#3-how-a-backtest-decides-things) (in the private `_simulate`, the one place exits are decided), then applies costs, splits and statistics. It raises `ValueError` on a position that is already closed or that opens before the first bar; these are never skipped silently.

- **`AmbiguityPolicy`**: `EXCLUDE` (`"exclude"`), `ASSUME_SL` (`"assume-sl"`), `ASSUME_TP` (`"assume-tp"`).
- **`PositionResolveDelay`**: `NEXT_BAR` (`"next-bar"`), `ENTRY_BAR` (`"entry-bar"`).

**`BacktestResult(trades, statistics)`** (frozen):

- `trades`: the positions frame with its result columns (and `split`), sorted by `open_dt`.
- `statistics`: the `statistics_by_split` table.

### 7.5 Application (files, provenance)

#### `application.load_historical_data_use_case`

| Function | Reads |
|---|---|
| `load_mt5(source, timeframe, symbol, *, progress=None)` | a folder of MT5 exports or one export; resampled per file and deduplicated across files (the pipeline's stage-0 build) |
| `load_clean_csv(path, timeframe, symbol)` | the research pipeline's clean CSV |
| `load_dukascopy(years, timeframe, symbol, *, data_dir=None, progress=None)` | Dukascopy bid/ask pairs; clock UTC, no volume columns |
| `load_source(source, timeframe, symbol, *, progress=None)` | clean CSV if `is_clean_csv(source)`, else MT5 |
| `is_clean_csv(path)` | whether the file's header starts with `datetime` |

All return a `HistoricalData` resampled to `timeframe`. Pass `progress=print` to see one line per file.

#### `backtest` (the CLI module, importable)

- **`run_backtest(backtest, out_dir, *, source=None) -> BacktestRun`**: runs the backtest and writes the four files. `BacktestRun` has `result`, `run_info` (the `run.json` content), `report` (the `statistics.txt` text) and `paths`.
- The three steps it chains, usable on their own:
  - `build_run_info(backtest, result, *, source=None)`
  - `format_report(result, run_info)`
  - `write_results(result, run_info, report, out_dir, *, price_decimals)`

---

## 8. Built-in strategies

### `narrow_asia_fade`: `strategies.narrow_asia_fade.NarrowAsiaFade`

The frozen v28 "Candle DNA — Narrow Asia London Fade". It reproduces v28 trade for trade; `tests/strategies/narrow_asia_fade/test_v28_parity.py` checks this on every `pytest` run. It needs broker-server-clock minute bars (M5 as researched) and raises on anything else.

| Parameter | Default | Meaning |
|---|---|---|
| `asia_start`, `asia_end` | 02:00, 10:00 | Asia window (end exclusive), broker-server time |
| `london_open` | 10:00 | breaks are looked for from here… |
| `study_end` | 14:00 | …up to and including the bar opening here; also the time stop (`exit_dt` = end of that bar) |
| `narrow_threshold_pips` | 21.72 | maximum Asia range (discovery Q1, frozen) |
| `rel_vol_min`, `rel_vol_length` | 1.6, 20 | break-bar tick volume over its 20-bar SMA must reach 1.6 |
| `stop_range_multiple` | 1.0 | stop distance = this × the Asia range |
| `max_missing_asia_bars` | 3 | tolerated gaps in the Asia window |

Run with `--ambiguity assume-sl --resolve-from next-bar` to match v28.

### `rsi_divergence`: `strategies.rsi_divergence.RsiDivergence`

Regular RSI divergences that leave the 30/70 band. It enters at the open of the bar after the pivot is confirmed, with the stop beyond the pivot's price extreme and the target at `risk_reward` × risk. Built on M15, timezone-agnostic.

| Parameter | Default | Meaning |
|---|---|---|
| `rsi_length` | 14 | Wilder RSI period |
| `pivot_left`, `pivot_right` | 5, 5 | pivot lookback / confirmation bars |
| `range_lower`, `range_upper` | 5, 60 | allowed bar distance between the two pivots |
| `rsi_lower`, `rsi_upper` | 30, 70 | the band the divergence must start outside and end inside |
| `risk_reward` | 2.0 | target distance ÷ stop distance |
| `stop_buffer_pips` | 1.0 | stop distance beyond the pivot bar's low (long) / high (short) |

Run with `--timeframe 15m --resolve-from entry-bar`.

---

## 9. Checklist and common mistakes

Before trusting a result:

- [ ] **No look-ahead.** Each entry uses only bars up to its own.
- [ ] **The right `--resolve-from`** for how the strategy enters ([5.3](#53-choosing---resolve-from-and---ambiguity)).
- [ ] **Costs included.** Never analyse `gross_pips` as if it were the result.
- [ ] **All three splits positive.** One good split is noise. Parameters were chosen on discovery only.
- [ ] **Enough trades per split** for the numbers to mean something.
- [ ] **`excluded_ambiguous` is small.** If not, compare `--ambiguity assume-sl` against `assume-tp`.
- [ ] **`run.json` kept with the results**, and the working tree committed (`"dirty": false`).

Common mistakes:

| Symptom | Cause |
|---|---|
| `ERROR: … windows are broker-server times; the data is on UTC` | a broker-clock strategy on Dukascopy data; convert the data to the broker clock with `shift_timezone`, or use MT5 data |
| `ERROR: SpreadCost needs a 'spread' column` | `--spread-cost` on the clean CSV, which has no spread; use `--cost-pips`, or MT5/Dukascopy data |
| `ValueError: long position needs sl < open_price < tp` | the strategy built a position with levels on the wrong side; skip such signals |
| `'datetime' must be strictly increasing` | the frame needs `clean_frame` before `HistoricalData` |
| far fewer trades than expected | a fixture or real bar touching a level counts as a hit/break; check the ≥ / ≤ edges |
| results with times 7 hours off | the data was treated as New York time; the broker clock is New York + 7h (`BROKER_SERVER_TZ`) |
| numbers look wrong on a finer `--timeframe` | resampling only coarsens: asking for `1m` from an M5 file returns M5 bars labelled 1m |
