# UI

The application's user interface is five command-line programs, one per task, plus a little presentation code they share. Each CLI has its own page. A CLI parses and validates its arguments, calls a [use case](../use-cases/README.md), prints the result and sets the exit code; it holds no business logic. Types and rules are in [conventions.md](../conventions.md).

In the Python code each CLI is an entry script at the repo root (`backtest.py`, …); its `main()` is the UI part.

| CLI | Page | Use case |
|---|---|---|
| `backtest` | [backtest.md](backtest.md) | RunBacktestFromConfig |
| `read_csv` | [read-csv.md](read-csv.md) | PrepareBars |
| `calculate_daily_sessions` | [calculate-daily-sessions.md](calculate-daily-sessions.md) | CollectDailySessions |
| `rsi_divergence` | [rsi-divergence.md](rsi-divergence.md) | ScanRsiDivergences |
| `show_symbols` | [show-symbols.md](show-symbols.md) | ListSymbols |
| (shared by the CLIs) | [shared-presentation.md](shared-presentation.md) | |

## Common behaviour

| Exit code | When |
|---|---|
| 0 | success |
| 1 | an expected error: printed as one line, `ERROR: {message}`, on standard error |
| 2 | a malformed argument, rejected by the argument parser before anything runs (usage line plus `{program}: error: {message}`) |

- Progress lines from the use cases go to standard output as they happen.
- `--help` describes every argument.
- Validation happens in two places. The **UI** checks what the argument parser can (types, choices, required arguments) and parses values into domain types (`SampleSize`, `Symbol`, `TimeZone`). Everything that needs the rest of the application (a config's contents, files on disk, a format's clock) is the use case's, and its errors reach the user as `ERROR:` lines.
- Each CLI catches only the errors it expects (listed below); anything else ends the program with a stack trace. A rewrite should report every use-case error as an `ERROR:` line.
