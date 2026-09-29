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

**Relative paths (`data.source`, `out`) are resolved against the config file's folder**, not the directory you run from, so a config gives the same run wherever it is launched.

## 2. Structure

A config is one JSON object. The root holds the run's settings; the nested `data` object describes the bars as they are on disk:

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

## 3. Keys

| Key | Required | Default | Meaning |
|---|---|---|---|
| `strategy` | yes | – | A key of `strategies.STRATEGIES`, e.g. `"narrow_asia_fade"`, `"rsi_divergence"`, `"session_breakout"`. |
| `data` | yes | – | The bars as they are on disk: an object with the `data.*` keys below. |
| `data.source` | yes | – | A file or a folder of files in `data.format`. |
| `data.format` | yes | – | How to read `data.source`:<br>`"metatrader"`: MT4/MT5 exports, a folder of them or one file.<br>`"dukascopy"`: Dukascopy bid/ask M1 pairs, a folder of them (searched recursively, so the whole export folder or one year of it) or either file of one pair.<br>`"clean-csv"`: the research pipeline's clean CSV (v24 output). |
| `data.symbol` | yes | – | Ticker of the source data, for pip size and price precision: `EURUSD`, `GBPUSD`, `AUDUSD`, `NZDUSD`, `USDCAD`, `USDCHF`, `USDJPY`, `XAUUSD`, `XAGUSD`. |
| `data.timeframe` | no | `"1m"` | Bar size of the source as stored: `"1m"` for raw MT5 exports and Dukascopy, `"5m"` for the pipeline clean CSV. Not read from the files: it is what the root `timeframe` is checked against. |
| `data.timezone` | no | `"UTC"` | The clock the source's timestamps are on: an IANA name (`"UTC"`, `"America/New_York"`, …) or `"broker"` for the MT5 broker-server clock (New York + 7h). It labels the bars and is never inferred from `data.format`: see [Data sources and clocks](running-a-backtest.md#4-data-sources-and-clocks) for the right value per source. Nothing is shifted, so a strategy with wall-clock windows must get data on the clock it expects. |
| `out` | yes | – | Output directory. Created if missing; existing result files are **overwritten**. What it receives is in [Reading the results](reading-the-backtest-results.md). |
| `timeframe` | no | `"5m"` | Bar size to test on: `5m`, `15m`, `1h`, `4h`, `1d`… (`m` minutes, `h` hours, `d` days, `w` weeks, `M` months). The source is resampled to it, so it must be a whole multiple of `data.timeframe` (`15m` from `5m`, not `1m` or `7m` from `5m`); anything else is rejected when the config loads (see [Checklist and common mistakes](README.md#checklist-and-common-mistakes)). |
| `cost_pips` | no | `1.7` | Fixed round-trip cost per trade, in pips (`FixedCost`). |
| `spread_cost` | no | `false` | `true`: charge each trade the bar's spread instead of `cost_pips` (`SpreadCost`). Needs data with a `spread` column: MT5 raw exports or Dukascopy, not the clean CSV. |
| `commission_pips` | no | `0` | With `spread_cost`: a flat commission added per trade. |
| `ambiguity` | no | `"exclude"` | A bar touching both SL and TP: `exclude`, `assume-sl` or `assume-tp`. See [Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity). |
| `resolve_from` | no | `"next-bar"` | First bar SL/TP are checked on: `next-bar` or `entry-bar`. See [Choosing `resolve_from` and `ambiguity`](running-a-backtest.md#3-choosing-resolve_from-and-ambiguity). |
| `splits` | no | `true` | `false`: report only "all", without the discovery/validation/test breakdown. |
| `strategy_parameters` | no | `{}` | Overrides for the strategy's own parameters (its dataclass fields, listed on each strategy's page); the rest keep their defaults. See [Strategy parameters](#4-strategy-parameters). |

## 4. Strategy parameters

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

Each key is one of the strategy's dataclass fields. Values are written as their JSON type — numbers, whole numbers, `true`/`false` and strings — and time-of-day fields as `"HH:MM"` strings, on the data's clock. Timezone-aware time fields (typed `ZonedTime`, such as RSI divergence's `start_time`) take `"HH:MM <zone>"` instead, where the zone is `"broker"` or an IANA name: `"08:00 Europe/London"`. A field that can be `None` (typed `X | None`) also takes `null`. Which types a strategy field may have to be settable from a config is in [Writing a new strategy](writing-a-strategy.md).

## 5. Validation

The config is checked before any data is read. Any of these prints `ERROR: <file>: …` and exits with code 1, rather than quietly running on a default:

- an unknown key (a typo such as `"ambigutiy"`);
- a value of the wrong JSON type;
- a missing required key, or an invalid choice;
- a `timeframe` that isn't a whole multiple of `data.timeframe`;
- a strategy parameter the strategy doesn't have or rejects (e.g. a negative `risk_reward`).

The same happens when the data and the strategy don't fit together:

- a broker-clock strategy on data whose `data.timezone` isn't `"broker"`;
- an invalid `data.timezone`, or a Dukascopy source with a non-UTC `data.timezone`;
- `spread_cost` without a spread column;
- a missing source, or an incomplete Dukascopy bid/ask pair;
- an unknown timeframe or symbol.

## 6. More examples

Both in `backtests/`:

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
