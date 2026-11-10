# External Formats

Every file the application reads or writes: the three bar-data formats, the backtest config file and the four result files. These are the contracts a rewrite must keep for existing data, configs and results to keep working. The [ports](ports/README.md) read and write them. Types and rules are in [conventions.md](conventions.md).

## Contents

1. [MetaTrader bar export](#1-metatrader-bar-export)
2. [histdata.com download](#2-histdatacom-download)
3. [Dukascopy candle export](#3-dukascopy-candle-export)
4. [Backtest config file](#4-backtest-config-file)
5. [Backtest result files](#5-backtest-result-files)

---

## 1. MetaTrader bar export

*Python: `libs/metatrader_csv/` (format), `ports/mt5_file_access/` (this repo's convention).* The CSV MetaTrader 4/5's "Export bars" produces, also used by other providers. One bar per line: a date, a time, the four prices, then up to three optional fields. Two shapes occur:

```
<DATE>	<TIME>	<OPEN>	<HIGH>	<LOW>	<CLOSE>	<TICKVOL>	<VOL>	<SPREAD>        MT5, with a header
2026.07.01	00:00:00	1.14209	1.14218	1.14166	1.14212	17	0	20

2020.01.02,00:00,1.12112,1.12112,1.12098,1.12098,10                             headerless
```

The fields, in MetaTrader's full order: `date`, `time`, `open`, `high`, `low`, `close`, `tick_volume`, `volume` (real volume, `<VOL>`), `spread` (in points). The first six are required.

### Reading

1. **Encoding:** UTF-8; a leading byte-order mark is ignored; undecodable bytes are replaced, never an error.
2. **Separator:** whichever of `,`, tab and `;` occurs most often in the first line; comma on a tie or when none occurs. Fields follow standard CSV quoting (double quotes).
3. **Blank lines** (no field with a non-space character) are skipped silently, anywhere.
4. **The layout is decided once, from the first non-empty row**, for the whole file:
   - It is a **header** when its first field starts with `<`, or normalises to `date` or `datetime` (normalise = trim, strip `<` and `>`, remove spaces, lower-case). Each header field is matched, normalised, against these spellings; the first column matching a field wins, and unknown names are ignored:

     | Field | Header spellings |
     |---|---|
     | `date` | `date` |
     | `time` | `time` |
     | `open`, `high`, `low`, `close` | `open`/`o`, `high`/`h`, `low`/`l`, `close`/`c` |
     | `tick_volume` | `tickvol`, `tickvolume`, `tick_volume` |
     | `volume` | `vol`, `volume`, `realvolume`, `real_volume` |
     | `spread` | `spread` |

     A header that doesn't name all six required fields is ignored: the columns are mapped by position, as below, using its column count. The header row itself is never data.
   - Otherwise the file is **headerless** and columns are mapped by count, MetaTrader's full order with the tail dropped:

     | Columns | Fields |
     |---|---|
     | 6 | `date` … `close` |
     | 7 | + `tick_volume` |
     | 8 | **ambiguous**: + `tick_volume`, `volume` or + `tick_volume`, `spread`. The format can't tell, so the reader must be told which, or it fails (`MT_AMBIGUOUS_LAYOUT`). This repo's MT5 broker exports end in the **spread**. |
     | 9 | + `tick_volume`, `volume`, `spread` |
     | any other | the first *n* fields of the full order (fewer than 6 means every line lacks prices; columns past the ninth are ignored) |
5. **Each data line:**
   - A field past the end of the line counts as blank; fields past the layout's width are ignored.
   - **Timestamp:** `date` (`YYYY.MM.DD`) and `time`, trimmed and joined by a space, read as `YYYY.MM.DD HH:MM`, then as `YYYY.MM.DD HH:MM:SS`. It carries no zone: the file doesn't say which clock it is on.
   - **Prices:** decimal numbers.
   - **Counts** (`tick_volume`, `volume`, `spread`): blank is `null` (not 0); otherwise read as a decimal number and **truncated** toward zero (`10.0` → 10, `12.7` → 12).
6. Rows are returned in file order: no sorting, no deduplication, no filling.

#### Malformed lines

A line is malformed when:

| Problem | Reason reported |
|---|---|
| a required field is blank or missing | `missing field(s): {names, comma-separated}` |
| the timestamp matches neither format | `unrecognized timestamp '{date} {time}'` |
| a price, or a non-blank count, is not a number | the number parser's message (Python: `could not convert string to float: '{text}'`) |

Read strictly, the first malformed line is an error (`MT_PARSE_ERROR`); otherwise it is dropped and reported with its exact line number, its fields re-joined with the separator, and the reason ([SkipHandler](ports/metatrader-bar-files.md#skiphandler)).

### Writing

1. Comma-separated, UTF-8, `\n` line endings, with a header row.
2. Columns: `date` (`YYYY.MM.DD`), `time` (`HH:MM`; **seconds are dropped**), then every other column of the table, in order, under its own name (`open,high,low,close,tick_volume,volume,spread`).
3. Prices: with `decimals`, fixed-point to that many places; otherwise the shortest decimal text that reads back as the same `Float` (`1.1211`, not `1.12110000000000004`).
4. Other numbers: integers as digits, floats as the shortest round-trip text; `null` is an empty field.

Read back by the MetaTrader reader, a written file gives the same table except for the dropped seconds and the truncated counts (so a fractional spread, such as a Dukascopy spread converted to points, comes back truncated to a whole point).

---

## 2. histdata.com download

*Python: `ports/histdata_file_access/`.* histdata.com's "MetaTrader" M1 downloads: plain headerless MetaTrader exports, read by the rules above.

- **Names:** `DAT_MT_{SYMBOL}_M1_{YYYYMM}.csv` (`DAT_MT_EURUSD_M1_202501.csv`). Each sits beside a `.txt` gap report, which is not a source; only names matching `DAT_MT_*.csv` are read.
- **Content:** 7 comma-separated columns, `date`, `time`, `open`, `high`, `low`, `close`, and a volume histdata always leaves at 0, which the port drops. No spread.
- **Clock:** `histdata` (`HISTDATA_TZ`): New York time until 2019-01-01, London − 5 hours from then on. Nothing in the file says so; the config or CLI must.

---

## 3. Dukascopy candle export

*Python: `libs/dukascopy_csv/`.* The CSVs [dukascopy-node](https://github.com/Leo4815162342/dukascopy-node) downloads. Each file holds **one price side** of one instrument over one period.

- **Names:** `{instrument}-{timeframe}-{side}-{start}-{end}.csv`, all lower case:

  | Part | Form | Example |
  |---|---|---|
  | `instrument` | letters and digits | `eurusd`, `deuidxeur` |
  | `timeframe` | letters and digits | `m1` |
  | `side` | `bid` or `ask` | |
  | `start` | `YYYY-MM-DD`, the first day covered | `2020-01-01` |
  | `end` | `YYYY-MM-DD` (exclusive) for a whole period, or `YYYY-MM-DDTHH-MM`, the download time of a partial one | `2020-02-01`, `2026-09-21T17-14` |

  The name is the only place the instrument and the side are recorded. Other files in a folder are ignored.
- **Content:** a CSV with a header, columns `timestamp,open,high,low,close`, plus `volume` when downloaded with volumes. `timestamp` is epoch **milliseconds**, UTC, as integers. A missing required column or a non-integer timestamp is `DUKASCOPY_FORMAT_ERROR`.
- **Pairs:** a bid file and an ask file are partners when they are in the same folder and share instrument, timeframe and start. Their ends may differ (each side of a partial download has its own download time).
- **Known anomalies,** passed on unchanged by the reader: a trading day missing on one side; a day of flat filler candles on the other; whole days without ask prices.
- **Clock:** UTC, always.

---

## 4. Backtest config file

*Python: `ports/backtest_config_access/`.* One JSON file drives one backtest. It is passed directly, or as a folder holding `backtest.json`. User documentation: `doc/backtest-framework/backtest-config.md`.

```json
{
    "strategy": {
        "name": "narrow_asia_fade",
        "parameters": {"rel_vol_min": 1.8, "study_end": "13:00"}
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
        "cost": {"commission_pips": 1.7}
    },
    "out": "output",
    "splits": "dvt"
}
```

### Keys

| Key | JSON type | Required | Default | Meaning |
|---|---|---|---|---|
| `strategy` | object | yes | | which strategy runs, and with what |
| `strategy.name` | string | yes | | a [registry](plugins/README.md#registry-and-parameters) name |
| `strategy.parameters` | object | no | `{}` | overrides of the strategy's parameters ([how values are written](use-cases.md#parameter-conversion)) |
| `data_source` | object | yes | | the bars as they are on disk |
| `data_source.path` | string | yes | | a file or a folder; relative to the config file's folder |
| `data_source.format` | string | yes | | `metatrader`, `histdata` or `dukascopy` |
| `data_source.symbol` | string | yes | | a ticker in `SYMBOLS` |
| `data_source.timeframe` | string | no | `1m` | the source's bar size as stored |
| `data_source.timezone` | string | no | `UTC` | the clock of the source's timestamps: `broker`, `histdata` or an IANA name; never inferred from `format` |
| `simulation` | object | no | all defaults | the rules the positions are traded under |
| `simulation.timeframe` | string | no | `5m` | the bar size to backtest on; a whole multiple of `data_source.timeframe` |
| `simulation.ambiguity` | string | no | `exclude` | `exclude`, `assume-sl` or `assume-tp` |
| `simulation.cost` | object | no | **no cost** | |
| `simulation.cost.spread` | boolean | no | `false` | charge each trade the spread of the bar where it crosses to the ask |
| `simulation.cost.commission_pips` | number >= 0 | no | `0` | pips charged on every trade; without `spread`, the whole cost |
| `out` | string | yes | | the results folder, relative to the config file's folder; **overwritten** |
| `splits` | string | no | `none` | `none`, `dvt`, `monthly` or `yearly`; groups the statistics only |

- An unknown key, a value of the wrong JSON type and a missing required key are errors, never ignored or defaulted. A boolean is never a number.
- Where SL/TP checking starts is not a setting: each position's `entry_fill`, chosen by the strategy, decides it.
- Every check and its error: [BacktestConfigSource](ports/backtest-config-source.md) (shape) and [LoadBacktestConfig](use-cases.md#3-loadbacktestconfig) (values).

---

## 5. Backtest result files

*Python: `backtest.py` (`write_results`, `format_report`).* A run writes four files into `out`, overwriting earlier ones. User documentation: `doc/backtest-framework/reading-the-backtest-results.md`.

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

One row per statistics row (`all` first, then each split in order), unrounded. Header: `split`, then the [metrics](domain-backtest.md#7-statistics) in order. Counts are written as integers.

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

The run's provenance, the [RunInfo](ports/backtest-result-store.md#runinfo) object: JSON indented with one tab per level, keys in RunInfo's order, a trailing newline. Values JSON has no type for (paths, times of day) are written as text.

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
