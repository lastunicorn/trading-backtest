# Use Cases

What the application does, as tasks that wire [ports](../ports/README.md), the [domain](../domain-backtest.md) and the [plugins](../plugins/README.md) together. Each use case has its own page, listing its input and output DTOs, its steps and the errors it can return. A use case never prints and never parses command-line arguments: it takes plain values, returns a result and reports progress through a callback ([conventions.md](../conventions.md#4-progress-reporting)). The CLIs that call them are in [ui.md](../ui.md).

In the Python code, a use case shared by several scripts (or too big for one) is a module in `application/`; the others are a function inside their entry script. Each page names where it lives.

| # | Use case | Called by | Python |
|---|---|---|---|
| 1 | [BuildCleanDataset](build-clean-dataset.md) | LoadHistoricalData, ScanRsiDivergences | `application/build_clean_dataset_use_case.py` |
| 2 | [LoadHistoricalData](load-historical-data.md) | RunBacktestFromConfig, CollectDailySessions | `application/load_historical_data_use_case.py` |
| 3 | [LoadBacktestConfig](load-backtest-config.md) | RunBacktestFromConfig | `application/load_backtest_config_use_case.py` |
| 4 | [RecordBacktest](record-backtest.md) | RunBacktestFromConfig, library callers | `backtest.py` (`run_backtest`) |
| 5 | [RunBacktestFromConfig](run-backtest-from-config.md) | `backtest` CLI | `backtest.py` (`_run`) |
| 6 | [PrepareBars](prepare-bars.md) | `read_csv` CLI | `read_csv.py` (`read_source` and `main`) |
| 7 | [ScanRsiDivergences](scan-rsi-divergences.md) | `rsi_divergence` CLI | `rsi_divergence.py` (`main`) |
| 8 | [CollectDailySessions](collect-daily-sessions.md) | `calculate_daily_sessions` CLI | `calculate_daily_sessions.py` (`collect_sessions`) |
| 9 | [ListSymbols](list-symbols.md) | `show_symbols` CLI | `show_symbols.py` |

## SourceFormat (Enum)

How a source's files are laid out, which picks the bar port. Shared by several use cases, the config's `data_source.format` and the CLIs' `--source-format`.

| Value | Wire | Files |
|---|---|---|
| `METATRADER` | `metatrader` | MetaTrader exports (`*.csv`): a folder of them, or one |
| `HISTDATA` | `histdata` | histdata.com downloads (`DAT_MT_*.csv`): a folder of them, or one |
| `DUKASCOPY` | `dukascopy` | Dukascopy bid/ask pairs: a folder of them (recursive), or one file of a pair |
