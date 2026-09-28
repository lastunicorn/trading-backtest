# Reading the Backtest Results

A companion to the [framework overview](README.md). How to produce these files is in [Running a backtest](running-a-backtest.md); before trusting a result, go through the [checklist](README.md#checklist-and-common-mistakes).

`--out` (or `run_backtest`) produces four files.

## `statistics.txt` — read this first

A header with the strategy, its parameters, the data, the source, the cost model, the simulation settings, the creation time and the git commit. Below it is the statistics table, one column per split, and a final line: *Net positive in every split: yes/no*.

For example, the end of the [Narrow Asia London Fade](strategy-narrow-asia-fade.md) report:

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

## `statistics.csv`

The same numbers, one row per split (`all`, `discovery`, `validation`, `test`), for comparing runs. The metrics, which are also the keys of [`compute_statistics()`](api-reference.md#domainpandas_approachstatistics):

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
| `split` | `discovery`, `validation` or `test` (absent with `--no-splits`) |

`close_dt` is the open time of the bar where SL/TP was hit (OHLC can't say when inside the bar). For a time stop it is `exit_dt` itself.

## `run.json`

Provenance: strategy name, class and parameters; data symbol, timeframe, clock, first/last bar and bar count; cost model, ambiguity and resolve-from settings; trade count; git commit and whether the working tree had uncommitted changes; creation time; source. Keep it with the results, so any number can be traced back to exactly what produced it.
