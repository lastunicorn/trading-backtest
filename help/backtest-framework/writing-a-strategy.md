# Writing a New Strategy

Read [how the framework works](README.md#how-it-works) and [how a backtest decides things](README.md#how-a-backtest-decides-things) first.

This guide builds a complete strategy step by step: a **London opening-range breakout**. The code below was run on the canonical dataset and its tests pass.

## Contents

1. [The contract](#1-the-contract)
2. [The strategy](#2-the-strategy)
3. [Register it for the CLI](#3-register-it-for-the-cli)
4. [Variants with different parameters](#4-variants-with-different-parameters)
5. [Test it](#5-test-it)
6. [Run it](#6-run-it)

---

## 1. The contract

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

## 2. The strategy

Create `strategies/opening_range_breakout.py`:

```python
"""London opening-range breakout -- the worked example from help/writing-a-strategy.md."""

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
- **Entry at the level.** The fill is inside the breaking bar, so this strategy should run with `"resolve_from": "next-bar"` (the default).
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

## 3. Register it for the CLI

Add it to `strategies/__init__.py`:

```python
from strategies.opening_range_breakout import OpeningRangeBreakout

STRATEGIES: dict[str, type[TradingStrategy]] = {
    "narrow_asia_fade": NarrowAsiaFade,
    "rsi_divergence": RsiDivergence,
    "session_breakout": SessionBreakout,
    "opening_range_breakout": OpeningRangeBreakout,
}
```

The key is the name a config's `strategy` accepts. The CLI builds the class with its default parameters, overridden by the config's `strategy_parameters` (next section).

## 4. Variants with different parameters

From the command line, set the fields in the config's `strategy_parameters`. Each dataclass field is a key; the values are checked against the field's type, and the strategy is built once while the config loads, so a `__post_init__` check fails before any data is read:

```json
"strategy_parameters": {"risk_reward": 2.0, "exit_at": "16:00"}
```

The config can set fields typed `int`, `float`, `bool`, `str` and `datetime.time` (as `"HH:MM"`). A field of any other type still works from Python but makes the config fail with a clear error; to support it, extend `_strategy_parameters` in `backtest.py`.

When a variant is worth keeping under its own name, register a subclass that changes the defaults instead:

```python
@dataclass(frozen=True)
class OpeningRangeBreakout2R(OpeningRangeBreakout):
    risk_reward: float = 2.0

STRATEGIES["opening_range_breakout_2r"] = OpeningRangeBreakout2R
```

From Python, just pass the values: `OpeningRangeBreakout(risk_reward=2.0, exit_at=time(16, 0))`.

## 5. Test it

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

## 6. Run it

Put a config in `backtests/opening_range_breakout/backtest.json`:

```json
{
	"strategy": "opening_range_breakout",
	"data": {
		"source": "../../output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv",
		"format": "clean-csv",
		"symbol": "EURUSD",
		"timeframe": "5m"
	},
	"out": "../../scratch/backtest_orb"
}
```

```bash
python3 backtest.py backtests/opening_range_breakout
```

For this example that gives 1,449 trades, a 49.3% win rate and profit factor 0.82: not profitable, but a working end-to-end run.
