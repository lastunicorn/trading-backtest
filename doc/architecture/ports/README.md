# Ports

The use cases' access to everything outside the process: data files, the config file, the result files, the wall clock and git. Each port has its own page, with its actions, its errors, the DTOs it hands over and, for the bar ports, the format library behind it. The exact file formats are in [external-formats.md](../external-formats.md). Types and rules are in [conventions.md](../conventions.md).

| Port | Page | Python | Used by |
|---|---|---|---|
| MetatraderBarFiles | [metatrader-bar-files.md](metatrader-bar-files.md) | `ports/mt5_file_access/` | BuildCleanDataset, PrepareBars |
| HistdataBarFiles | [histdata-bar-files.md](histdata-bar-files.md) | `ports/histdata_file_access/` | LoadHistoricalData, PrepareBars |
| DukascopyBarFiles | [dukascopy-bar-files.md](dukascopy-bar-files.md) | `ports/dukascopy_file_access/` | LoadHistoricalData, PrepareBars |
| FileSystem | [file-system.md](file-system.md) | `ports/file_system_access/` | BuildCleanDataset, PrepareBars |
| BacktestConfigSource | [backtest-config-source.md](backtest-config-source.md) | `ports/backtest_config_access/` | LoadBacktestConfig |
| RunEnvironment | [run-environment.md](run-environment.md) | `ports/run_environment/` | RecordBacktest |
| BacktestResultStore | [backtest-result-store.md](backtest-result-store.md) | `backtest.py` (`write_results`) | RecordBacktest |

## What a port does

These rules hold for every port:

- **A port parses and stops.** It returns what the file holds, in the application's shape. It never sorts, deduplicates, fills, resamples or shifts a clock: those are domain decisions ([domain-market-data.md](../domain-market-data.md#7-bar-table-operations)).
- **A port may hand over a domain entity** it parses into (`Bar`), never call domain logic.
- **The format itself lives in a library** ([metatrader_csv](metatrader-bar-files.md#format-library-metatrader_csv), [dukascopy_csv](dukascopy-bar-files.md#format-library-dukascopy_csv)) that knows nothing of this application; the port adds what is specific to it (which of two ambiguous layouts this broker uses, which columns are noise).
- **Use cases receive ports as parameters** (in Python: functions passed in, such as `read_file`, `now`, `git_commit`), so tests pass fakes. A rewrite should define each port as an interface and inject it.
- **A DTO is described on the page of the port that hands it over.** Where another port uses it too, that page links to it (`SkipHandler`, for example, is on the MetatraderBarFiles page and also used by HistdataBarFiles).
