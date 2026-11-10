# BacktestResultStore

A [port](README.md) of the [application blueprint](../README.md).

*Python: `backtest.py`'s `write_results`.* In the Python code this lives in the entry script rather than under `ports/`; a rewrite should put it behind a port like the others.

## Actions

| Action | Returns | Description |
|---|---|---|
| `write_results(result: BacktestResult, run_info: RunInfo, report: String, out_dir: Path, price_decimals: Integer)` | `List<Path>` | Creates `out_dir` if needed and writes, **overwriting**, `positions.csv`, `statistics.txt`, `statistics.csv` and `run.json`, returned in that order. Prices in `positions.csv` are rounded to `price_decimals` (the symbol's), pips to 2 places, `net_r` to 3, `duration_min` to 1. Formats: [below](#file-format-backtest-result-files). |

## Errors

| Code | Description |
|---|---|
| `OUTPUT_WRITE_FAILED` | Any failure to create the folder or write a file. |

## DTOs

`BacktestResult` is a domain type ([domain/backtest.md](../domain/backtest.md#backtestresult)).

### RunInfo

The provenance of one backtest run, built by [RecordBacktest](../use-cases/record-backtest.md) and written as `run.json`. A JSON object, keys in this order:

| Key | Type | Content |
|---|---|---|
| `created` | `String` | `now()`, ISO 8601 to the second (`2026-11-09T13:21:25`) |
| `strategy.name` | `String` | the config's `strategy.name`, or the strategy's own `name` when none was given |
| `strategy.class` | `String` | the strategy's fully qualified class name (`strategies.narrow_asia_fade.NarrowAsiaFade`) |
| `strategy.parameters` | `Map<String, Any>` | every parameter, in the spelling a config reads back ([recording parameters](../plugins/README.md#recording-parameters)) |
| `data.symbol` | `String` | ticker |
| `data.timeframe` | `String` | `SampleSize` text |
| `data.timezone` | `String` | the clock's **display name** (`broker-server (America/New_York+7h)`, `UTC`) |
| `data.first_bar`, `data.last_bar` | `String` | ISO 8601 (`2020-01-02T00:00:00`) |
| `data.bars` | `Integer` | |
| `simulation.cost_model` | `Map` | `class` (`FixedCost` / `SpreadCost`) followed by its properties (`pips` / `commission_pips`) |
| `simulation.ambiguity_policy` | `String` | wire value |
| `splits` | `String` | wire value |
| `trades` | `Integer` | number of trades |
| `git` | `Map` | `commit`, `dirty` from [`GitCommit`](run-environment.md#gitcommit) |
| `source` | `String` | only when given: `{data_source.path} ({format})` from the CLI |
| `notes` | `List<String>` | only when there are any: `BacktestResult.notes` |

## File format: Backtest result files

*Python: `format_report` (`backtest.py`) lays out `statistics.txt`.* A run writes four files into `out`, overwriting earlier ones. User documentation: `doc/backtest-framework/reading-the-backtest-results.md`.

CSV conventions for both CSV files: comma-separated, header row, `\n` line endings, minimal quoting (a field containing a comma or quote is quoted), no index column. A `null` or `NaN` is an empty field; `+∞` is `inf`. Floats are written as the shortest text that reads back as the same `Float`.

### `positions.csv`

One row per trade, sorted by `open_dt`. Columns, in this order:

| Column | Format | Notes |
|---|---|---|
| `open_dt` | `YYYY-MM-DD HH:MM:SS` | |
| `side` | `long` / `short` | |
| `open_price`, `sl`, `tp` | rounded to the symbol's `price_decimals` | |
| `entry_fill` | `at-level` / `at-open` | |
| `exit_dt` | `YYYY-MM-DD HH:MM:SS` | empty when none |
| `close_dt` | `YYYY-MM-DD HH:MM:SS` | the hitting bar's open time; `exit_dt` for a time stop |
| `close_price` | rounded to `price_decimals` | empty for `ambiguous` |
| `outcome` | an outcome wire value | |
| `tag` | text | the strategy's label |
| `gross_pips`, `cost_pips`, `net_pips`, `risk_pips` | rounded to 2 places | `gross_pips`/`net_pips` empty for `ambiguous` |
| `net_r` | rounded to 3 places | empty for `ambiguous` |
| `duration_min` | rounded to 1 place | |
| `split` | the split's name | only with a split mode other than `none` |

Example:

```
open_dt,side,open_price,sl,tp,entry_fill,exit_dt,close_dt,close_price,outcome,tag,gross_pips,cost_pips,net_pips,risk_pips,net_r,duration_min,split
2020-01-07 09:47:00,long,13212.295,13172.9,13330.48,at-level,2020-01-07 16:30:00,2020-01-07 14:43:00,13172.9,stop-loss-hit,retest-high,-39.4,1.2,-40.6,39.4,-1.031,296.0,discovery
```

### `statistics.csv`

One row per statistics row (`all` first, then each split in order), unrounded. Header: `split`, then the [metrics](../domain/backtest.md#7-statistics) in order. Counts are written as integers.

### `statistics.txt`

The human report, also printed by the `backtest` CLI. Lines:

```
==============================================================================      ← 78 '='
BACKTEST -- {strategy.name}
==============================================================================
Parameters:  {name=value, …}                                 ← "none" without parameters
Data:        {symbol} {timeframe}, {bars} bars, {first_bar} -> {last_bar} ({timezone display name})
Source:      {source}                                        ← only when recorded
Costs:       {cost class}({name=value, …}) per trade, net of every P&L figure
Simulation:  ambiguous bars {ambiguity policy}
Created:     {created}   git {commit, or n/a}                ← + " (uncommitted changes)" when dirty

A win is net_pips > 0 after costs. Ambiguous trades are counted but carry no P&L.

{statistics table}

{verdict}                                                    ← with a split mode only

Notes:                                                       ← only with notes
- {note}
```

The file ends with a newline. `{bars}` has thousands separators. Values come from `run.json`'s fields; parameter and cost values are written as the Python code prints them (booleans `True`/`False`, null `None`, floats in shortest form: `1.7`, `0.0`).

**Cell format.** Each statistic is formatted by the first rule that applies to its value and name:

| Rule | Format | Example |
|---|---|---|
| NaN | `n/a` | |
| ±∞ | `inf` | |
| name ends `_pct` | 1 decimal + `%` | `72.0%` |
| name ends `_pips` | thousands separators, 1 decimal | `-4,574.1` |
| `profit_factor` | 2 decimals | `1.37` |
| name ends `_r` | 3 decimals | `-0.220` |
| name ends `_min` | thousands separators, 0 decimals | `89` |
| otherwise (counts) | integer, thousands separators | `2,889` |

**Table, split modes `none` and `dvt`:** one row per metric, one column per statistics row (`all`, then the splits). The metric column is as wide as the longest metric name (`outcome_take-profit-hit`, 23 characters), left-aligned, followed by two spaces; each value column is 12 characters, right-aligned. The header line is blank over the metric column and holds the split names; under it, a rule of `-` as long as the table.

```
                                  all   discovery  validation        test
-------------------------------------------------------------------------
trades                            982         580         203         199
win_rate_pct                    22.7%       23.4%       21.7%       21.6%
```

**Table, split modes `monthly` and `yearly`:** turned around, since there are too many periods for a column each. One row per statistics row (`all`, then each period), one column per key metric: `trades`, `win_rate_pct`, `total_net_pips`, `total_net_r`, `profit_factor`, `expectancy_r`, `max_drawdown_pips` (`statistics.csv` keeps them all). The label column is as wide as the longest label, left-aligned; each metric column is as wide as `max(len(name), 10)`, right-aligned, preceded by two spaces. A rule of `-` as long as the header line follows the header.

```
          trades  win_rate_pct  total_net_pips  total_net_r  profit_factor  expectancy_r  max_drawdown_pips
-----------------------------------------------------------------------------------------------------------
all          207         72.0%           257.5       16.140           1.37         0.078               70.5
2020          30         86.7%           139.5        8.068           4.63         0.269               20.0
```

**Verdict:**

| Split mode | Line |
|---|---|
| `none` | none |
| `dvt` | `Net positive in every split ({split names, comma-separated}): {yes \| no}`: `yes` when every split's `total_net_pips > 0` (a NaN counts as not) |
| `monthly`, `yearly` | `Net positive in {k} of {n} {months \| years} with trades ({m} without)`: `n` periods with trades, `k` of them with `total_net_pips > 0`, `m` periods without trades |

### `run.json`

The run's provenance, the [RunInfo](#runinfo) object: JSON indented with one tab per level, keys in RunInfo's order, a trailing newline. Values JSON has no type for (paths, times of day) are written as text.

```json
{
	"created": "2026-11-09T13:21:25",
	"strategy": {
		"name": "orb_retest_entry",
		"class": "strategies.orb_retest_entry.OrbRetestEntry",
		"parameters": {"session": "London", "opening_range_minutes": 15, "order_expiry_minutes": 120, "exit_at_session_end": true, "risk_reward": 3.0}
	},
	"data": {"symbol": "DEUIDXEUR", "timeframe": "1m", "timezone": "UTC", "first_bar": "2020-01-01T00:00:00", "last_bar": "2026-08-31T23:59:00", "bars": 2889871},
	"simulation": {"cost_model": {"class": "SpreadCost", "commission_pips": 0.0}, "ambiguity_policy": "exclude"},
	"splits": "dvt",
	"trades": 982,
	"git": {"commit": "75a05b6", "dirty": true},
	"source": "/data/dukascopy/deuidxeur (dukascopy)",
	"notes": ["11 trade(s) charged 0 spread: …"]
}
```

(Nested objects are shown on one line here for brevity; the file puts every key on its own line.)

`data.timezone` is the clock's display name (`broker-server (America/New_York+7h)` for the broker clock), not the config spelling (`broker`).
