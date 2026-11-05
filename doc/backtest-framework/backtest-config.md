# The Backtest Config File

A companion to [Running a backtest](running-a-backtest.md). Every setting of a `backtest.py` run lives in one JSON config file; the command takes only its path. This page describes that file: its structure, every key, how it is validated, and ready-made examples.

## Contents

1. [Where configs live](#1-where-configs-live)
2. [Structure](#2-structure)
3. [Keys](#3-keys)
4. [Strategy parameters](#4-strategy-parameters)
5. [Validation](#5-validation)
6. [More examples](#6-more-examples)

---

## 1. Where configs live

```bash
python3 backtest.py backtests/narrow_asia_fade/backtest.json
python3 backtest.py backtests/narrow_asia_fade        # a folder: reads the backtest.json inside it
```

Ready-made configs live in `backtests/<name>/backtest.json`.

**Relative paths (`data_source.path`, `out`) are resolved against the config file's folder**, not the directory you run from, so a config gives the same run wherever it is launched.

## 2. Structure

A config is one JSON object, grouped by what each setting controls:

- `strategy` names the registered strategy to run and overrides its parameters;
- `data_source` describes the bars as they are on disk;
- `simulation` holds the rules the positions are traded under: the bar size to test on, how exits are resolved, and in its nested `cost` object what each trade pays;
- the root keeps how to break the statistics down (`splits`) and where to write the results (`out`).

```json
{
	"strategy": {
		"name": "narrow_asia_fade"
	},
	"data_source": {
		"path": "../../data/eurusd/1min",
		"format": "metatrader",
		"symbol": "EURUSD",
		"timeframe": "1m",
		"timezone": "broker"
	},
	"simulation": {
		"timeframe": "5m",
		"ambiguity": "assume-sl",
		"resolve_from": "next-bar",
		"cost": {
			"commission_pips": 1.7
		}
	},
	"splits": "dvt",
	"out": "output"
}
```

## 3. Keys

| Key | Required | Default | Meaning |
|---|---|---|---|
| `strategy` | yes | – | The strategy to run: an object with the `strategy.*` keys below. |
| `strategy.name` | yes | – | A key of `strategies.STRATEGIES`, e.g. `"narrow_asia_fade"`, `"orb_break_entry"`, `"rsi_divergence"`, `"session_breakout"`. Also recorded as `strategy.name` in `run.json` and shown in the report header. |
| `strategy.parameters` | no | `{}` | Overrides for the strategy's own parameters (its dataclass fields, listed on each strategy's page); the rest keep their defaults. See [Strategy parameters](#4-strategy-parameters). |
| `data_source` | yes | – | The bars as they are on disk: an object with the `data_source.*` keys below. |
| `data_source.path` | yes | – | A file or a folder of files in `data_source.format`. |
| `data_source.format` | yes | – | How to read `data_source.path`:<br>`"metatrader"`: MT4/MT5 exports, a folder of them or one file.<br>`"histdata"`: histdata.com MetaTrader downloads (`DAT_MT_*.csv`), a folder of them or one file; no volume, no spread; `data_source.timezone` should be `"histdata"`.<br>`"dukascopy"`: Dukascopy bid/ask M1 pairs, a folder of them (searched recursively, so the whole export folder or one year of it) or either file of one pair. |
| `data_source.symbol` | yes | – | Ticker of the source data, for pip size and price precision: `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDCAD`, `USDCHF`, `USDJPY`, `XAUUSD`, `XAGUSD`. |
| `data_source.timeframe` | no | `"1m"` | Bar size of the source as stored: `"1m"` for raw MT5 exports and Dukascopy, `"5m"` for a `read_csv.py --timeframe 5m --output` file. Not read from the files: it is what `simulation.timeframe` is checked against. |
| `data_source.timezone` | no | `"UTC"` | The clock the source's timestamps are on: an IANA name (`"UTC"`, `"America/New_York"`, …), `"broker"` for the MT5 broker-server clock (New York + 7h) or `"histdata"` for histdata.com downloads (New York's clock, on the EU daylight-saving dates from 2019). It labels the bars and is never inferred from `data_source.format`: see [Data sources and clocks](running-a-backtest.md#4-data-sources-and-clocks) for the right value per source. Nothing is shifted, so a strategy with wall-clock windows must get data on the clock it expects. |
| `out` | yes | – | Output directory. Created if missing; existing result files are **overwritten**. What it receives is in [Reading the results](reading-the-backtest-results.md). |
| `simulation` | no | all defaults | The rules the positions are traded under: an object with the `simulation.*` keys below. |
| `simulation.timeframe` | no | `"5m"` | Bar size to test on: `5m`, `15m`, `1h`, `4h`, `1d`… (`m` minutes, `h` hours, `d` days, `w` weeks, `M` months). The source is resampled to it, so it must be a whole multiple of `data_source.timeframe` (`15m` from `5m`, not `1m` or `7m` from `5m`); anything else is rejected when the config loads (see [Checklist and common mistakes](README.md#checklist-and-common-mistakes)). |
| `simulation.ambiguity` | no | `"exclude"` | A bar touching both SL and TP: `exclude`, `assume-sl` or `assume-tp`. See [Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity). |
| `simulation.resolve_from` | no | `"next-bar"` | First bar SL/TP are checked on: `next-bar` or `entry-bar`. See [Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity). |
| `simulation.cost` | no | no cost | What each trade pays: an object with the `simulation.cost.*` keys below. Leaving it out, or leaving it empty, backtests with **zero cost**; `narrow_asia_fade`'s round-trip friction is `"cost": {"commission_pips": 1.7}`. |
| `simulation.cost.spread` | no | `false` | `true`: charge each trade the spread of the bar where it crosses to the ask, entry for a long and exit for a short (`SpreadCost`). Needs data with a `spread` column: MT5 raw exports or Dukascopy, not histdata.com exports. A bar without a spread value (a Dukascopy minute with no ask price) is charged 0 spread, listed in the report's Notes. |
| `simulation.cost.commission_pips` | no | `0` | A flat round-trip cost per trade, in pips. Without `simulation.cost.spread` it is the whole cost (`FixedCost`); with it, it is added to the spread. |
| `splits` | no | `"none"` | How the statistics are broken down besides "all" (it groups trades, it changes none of them, so it is not a `simulation` key):<br>`"none"`: only "all".<br>`"dvt"`: the chronological 60/20/20 discovery / validation / test cut, over the strategy's `split_days`.<br>`"monthly"` / `"yearly"`: one group per calendar month (`2024-03`) or year (`2024`), including periods without trades.<br>See [Reading the results](reading-the-backtest-results.md) for how each is reported. |

## 4. Strategy parameters

A variant of a strategy only needs `strategy.parameters`; the report header and `run.json` record the full parameter set the run used:

```json
{
	"strategy": {
		"name": "narrow_asia_fade",
		"parameters": {"study_end": "13:00", "rel_vol_min": 1.8}
	},
	"data_source": {
		"path": "../../data/eurusd/1min",
		"format": "metatrader",
		"symbol": "EURUSD",
		"timeframe": "1m",
		"timezone": "broker"
	},
	"simulation": {"ambiguity": "assume-sl"},
	"out": "../../scratch/backtest_narrow_asia_fade_1300"
}
```

Each key of `strategy.parameters` is one of the strategy's dataclass fields. Values are written as their JSON type — numbers, whole numbers, `true`/`false` and strings — and time-of-day fields as `"HH:MM"` strings, on the data's clock. Timezone-aware time fields (typed `ZonedTime`, such as RSI divergence's `start_time`) take `"HH:MM <zone>"` instead, where the zone is `"broker"` or an IANA name: `"08:00 Europe/London"`. A `TradingSession` field (ORB's `session`) takes a session's name from `domain.trading_session.SESSIONS`: `"Tokyo"`, `"Asia"`, `"London"` or `"New York"`. A field that can be `None` (typed `X | None`) also takes `null`. Which types a strategy field may have to be settable from a config is in [Writing a new strategy](writing-a-strategy.md).

## 5. Validation

The config is checked before any data is read. Any of these prints `ERROR: <file>: …` and exits with code 1, rather than quietly running on a default:

- an unknown key (a typo such as `"ambigutiy"`, or a `simulation` key such as `"timeframe"` written at the root);
- a value of the wrong JSON type;
- a missing required key, or an invalid choice;
- a `simulation.timeframe` that isn't a whole multiple of `data_source.timeframe`;
- a strategy parameter the strategy doesn't have or rejects (e.g. a negative `risk_reward`).

The same happens when the data and the strategy don't fit together:

- a broker-clock strategy on data whose `data_source.timezone` isn't `"broker"`;
- an invalid `data_source.timezone`, or a Dukascopy source with a non-UTC `data_source.timezone`;
- `"simulation": {"cost": {"spread": true}}` without a spread column;
- a missing source, or an incomplete Dukascopy bid/ask pair;
- an unknown timeframe or symbol.

## 6. More examples

Both in `backtests/`:

```json
// backtests/rsi_divergence_15m/backtest.json: M15 bars rebuilt from raw M1 exports; entries are at a bar's open
{
	"strategy": {"name": "rsi_divergence"},
	"data_source": {"path": "../../data/eurusd/1min", "format": "metatrader", "symbol": "EURUSD", "timezone": "broker"},
	"simulation": {"timeframe": "15m", "resolve_from": "entry-bar"},
	"out": "../../scratch/backtest_rsi_divergence"
}

// backtests/rsi_divergence_dukascopy/backtest.json: the same on Dukascopy data, charging the real spread plus a commission
{
	"strategy": {"name": "rsi_divergence"},
	"data_source": {"path": "/path/to/dukascopy/eurusd/2025", "format": "dukascopy", "symbol": "EURUSD"},
	"simulation": {
		"timeframe": "15m",
		"resolve_from": "entry-bar",
		"cost": {"spread": true, "commission_pips": 0.2}
	},
	"out": "../../scratch/backtest_rsi_duka"
}
```

(JSON itself has no comments; they are only labels here.)
