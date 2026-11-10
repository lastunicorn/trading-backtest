# `read_csv`

A [CLI](README.md) of the [application blueprint](../README.md).

*Python: `read_csv.py`.* Prints a bar source as a table, raw or processed, or writes the processed bars to a MetaTrader-format CSV. Use case: [PrepareBars](../use-cases/prepare-bars.md).

```
read_csv <source> [--source-format F] [--source-timezone TZ] [--source-symbol TICKER]
                  [--timezone TZ] [--timeframe SIZE] [--decimals N]
                  [--rows N] [--all] [--tail] [--output PATH] [--strict]
```

| Argument | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | required | a file or a folder of exports |
| `--source-format` | `SourceFormat` | `metatrader` | `metatrader`, `histdata` or `dukascopy` |
| `--source-timezone` | `TimeZone` | `broker` | the files' clock; only `--timezone` uses it |
| `--source-symbol` | ticker | none | sets the price decimals; required for `dukascopy` (its tick size converts the spread to points) |
| `--timezone` | `TimeZone` | none | shift the bars to this clock; none keeps the source's |
| `--timeframe` | `SampleSize` text | none | resample; none keeps the raw bars |
| `--decimals` | `Integer` | none | price decimals for display and `--output`; overrides `--source-symbol` |
| `--rows` | `Integer` | 20 | bars shown; a negative value shows none |
| `--all` | flag | off | show every bar (overrides `--rows`) |
| `--tail` | flag | off | show the last bars instead of the first |
| `--output` | `Path` | none | write the full processed table there instead of displaying it (ignores `--rows`/`--all`/`--tail`) |
| `--strict` | flag | off | abort on a malformed line instead of skipping it (`metatrader`, `histdata`; a bad Dukascopy file always aborts) |

## Validation, in order

| Input | Rule | On failure |
|---|---|---|
| `--source-format` | one of the three choices | exit 2 |
| `--decimals`, `--rows` | whole numbers | exit 2 |
| `--timezone`, `--source-timezone` | `timezone_by_name` resolves it ([`timezone_arg`](shared-presentation.md#timezone_arg)) | exit 2: `argument --timezone: unknown timezone '{name}': expected 'broker', 'histdata' or an IANA name such as 'UTC' or 'Europe/London'` |
| `--timeframe` | parses as `SampleSize` | `ERROR: {INVALID_INTERVAL message}`, exit 1 |
| `--source-symbol` | in `SYMBOLS` | `ERROR: unknown symbol ticker '{ticker}'`, exit 1 |
| `dukascopy` + `--source-symbol` | required | `ERROR:` `DUKASCOPY_NEEDS_SYMBOL`, exit 1 |
| `dukascopy` + `--source-timezone` | UTC all year | `ERROR:` `CLOCK_NOT_UTC`, exit 1 |

Price decimals: `--decimals`, else the symbol's `price_decimals`, else the default number formatting.

Errors caught (exit 1): any error from reading (`NO_SOURCE_FILES`, `MT_PARSE_ERROR` with `--strict`, a bad file), and `NO_BARS_FOUND`.

## Output

```
================================================================
SOURCE: {source}  ({format}, {n} files)          ← ", {n} files" only when n > 1
RESAMPLE: {timeframe}                            ← only with --timeframe
TIMEZONE: {source clock} -> {target clock}       ← only with --timezone
================================================================
Timezone: {clock name the bars are on}
Bars:   {count, thousands separators}
First:  {YYYY.MM.DD HH:MM}
Last:   {YYYY.MM.DD HH:MM}
Span:   {whole days from first to last} days
Skipped: {n} malformed line(s) -- first at line {line_no}: {reason}   ← only when lines were skipped
```

Then, with `--output`, a blank line and `Written: {path}`; otherwise the bar table ([`display_frame`](shared-presentation.md#display_frame)). Last, a blank line, `Data processing time: {s}s` (reading through resampling) and `Total execution time: {s}s`, both to 2 decimals.
