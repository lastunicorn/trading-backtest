# Reading the Backtest Results

A companion to the [framework overview](README.md). How to produce these files is in [Running a backtest](running-a-backtest.md); before trusting a result, go through the [checklist](README.md#checklist-and-common-mistakes).

A run writes four files into the config's `out` folder (or `run_backtest`'s `out_dir`).

## `statistics.txt` — read this first

A header with the strategy, its parameters, the data, the source, the cost model, the simulation settings, the creation time and the git commit. Below it is the statistics table. Its layout depends on the config's [`splits`](backtest-config.md#3-keys):

- `"none"`: one column, `all`.
- `"dvt"`: one column per split and a final line, *Net positive in every split: yes/no*.
- `"monthly"` / `"yearly"`: too many periods for a column each, so the table is turned around: one row per period and six key metrics as columns (every metric is still in `statistics.csv`). The final line counts the periods that made money: *Net positive in K of N months with trades (E without)*.

For example, the end of the [Narrow Asia London Fade](strategy-narrow-asia-fade.md) report with `"splits": "dvt"`:

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

And with `"splits": "yearly"`:

```
          trades  win_rate_pct  total_net_pips  profit_factor  expectancy_r  max_drawdown_pips
----------------------------------------------------------------------------------------------
all          207         72.0%           257.5           1.37         0.078               70.5
2020          30         86.7%           139.5           4.63         0.269               20.0
2021          53         66.0%            10.3           1.05         0.017               70.5
...
2026          12         75.0%            30.8           2.86         0.186               10.9

Net positive in 6 of 7 years with trades (0 without)
```

## `statistics.csv`

The same numbers, one row for `all` and then one per split (`discovery`, `validation`, `test`; or `2024-03`…; or `2024`…), always with every metric, for comparing runs. The metrics, which are also the keys of [`compute_statistics()`](api-reference.md#domainpandas_approachstatistics):

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

## `positions.csv`

One row per trade, sorted by entry time:

| Column | Meaning |
|---|---|
| `open_dt`, `side`, `open_price`, `sl`, `tp`, `exit_dt` | what the strategy asked for |
| `close_dt`, `close_price`, `outcome` | what the simulator decided (`close_price` is empty for `ambiguous`) |
| `tag` | the strategy's free-text label |
| `gross_pips`, `cost_pips`, `net_pips` | result before costs, the cost, result after costs |
| `risk_pips`, `net_r` | entry-to-stop distance, and net pips ÷ risk |
| `duration_min` | minutes from `open_dt` to `close_dt` |
| `split` | the trade's split: `discovery`, `validation` or `test` with `"splits": "dvt"`, `2024-03` with `"monthly"`, `2024` with `"yearly"` (absent with `"none"`) |

`close_dt` is the open time of the bar where SL/TP was hit (OHLC can't say when inside the bar). For a time stop it is `exit_dt` itself.

## `run.json`

Provenance: strategy name, class and parameters; data symbol, timeframe, clock, first/last bar and bar count; cost model, ambiguity and resolve-from settings; trade count; git commit and whether the working tree had uncommitted changes; creation time; source. Keep it with the results, so any number can be traced back to exactly what produced it.
