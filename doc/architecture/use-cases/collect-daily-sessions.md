# CollectDailySessions

A [use case](README.md) of the [application blueprint](../README.md).

The open, high, low and close of each chosen trading session on every day of a source.

## Input

| Field | Type | Default | Notes |
|---|---|---|---|
| `source` | `Path` | | a folder or one file |
| `source_format` | `SourceFormat` | | |
| `sessions` | `List<TradingSession>` | | |
| `symbol` | `Symbol` | `EURUSD` | |
| `source_timezone` | `TimeZone` | | labels the timestamps; nothing is shifted |
| `progress` | callback? | | |

## Output

`Map<TradingSession, Table<SessionOhlcRow>>`, in `sessions` order; each table has one row per day whose session has at least one bar ([`session_ohlc`](../domain-market-data.md#7-bar-table-operations)).

## Steps

1. `data = LoadHistoricalData(source, source_format, timeframe = 1m, symbol, source_timezone, progress)`. At M1 sources' own size the resample is a no-op (a coarser source is relabelled, see LoadHistoricalData).
2. For each session: `session_ohlc(data.data, session, timezone = data.timezone)`.

## Errors

Those of LoadHistoricalData.
