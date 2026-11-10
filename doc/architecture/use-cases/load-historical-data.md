# LoadHistoricalData

A [use case](README.md) of the [application blueprint](../README.md).

Bars from any supported source → `HistoricalData`. This is where the sources' differences are settled: which port reads them, and which unit their spread is in. The clock is **not** a property of the format: the caller states it, and it labels the bars without shifting them.

## Input

| Field | Type | Notes |
|---|---|---|
| `source` | `Path` | a folder or one file |
| `source_format` | `SourceFormat` | |
| `timeframe` | `SampleSize` | the bar size wanted |
| `symbol` | `Symbol` | |
| `timezone` | `TimeZone` | the clock of the source's timestamps |
| `progress` | callback? | |

## Output

`HistoricalData` (`data` resampled to `timeframe`, spread in pips, on the `timezone` clock).

## Steps

- **`METATRADER`:** `table = BuildCleanDataset(source, timeframe, read_file = MetatraderBarFiles.read_frame)`; return `HistoricalData.from_frame(table, timeframe, symbol, spread_unit = POINTS, timezone)`.
- **`HISTDATA`:** `table = BuildCleanDataset(source, timeframe, pattern = "DAT_MT_*.csv", read_file = HistdataBarFiles.read_frame)`; return `HistoricalData.from_frame(table, timeframe, symbol, timezone)`. The bars have no volume and no spread. Any clock is accepted (`histdata` is right; nothing checks it).
- **`DUKASCOPY`:**
  1. `timezone` must be UTC all year (`is_utc`), since epoch timestamps can only be UTC: `CLOCK_NOT_UTC` otherwise.
  2. Progress `Reading Dukascopy {source}...`.
  3. `table = DukascopyBarFiles.read_path(source)`, minus its always-empty `tick_volume` and `volume` columns (so they aren't resampled into zeros).
  4. Return `HistoricalData.from_frame(resample_ohlc(clean_frame(table), timeframe), timeframe, symbol, spread_unit = PRICE, timezone)`.

Resampling to the source's own bar size is a no-op. Asking for a size **finer** than the source cannot be detected here and silently relabels the bars (M5 bars come back labelled `1m`); LoadBacktestConfig prevents it for backtests by checking `simulation.timeframe` against `data_source.timeframe`.

## Errors

| Code | Description |
|---|---|
| `CLOCK_NOT_UTC` | Dukascopy with a non-UTC clock: `Dukascopy bars are UTC (epoch timestamps), not {timezone}`. |
| `NO_USABLE_SOURCE_FILES` | From BuildCleanDataset (`METATRADER`, `HISTDATA`). |
| `DUKASCOPY_*` | From [DukascopyBarFiles](../ports/dukascopy-bar-files.md). |
| `NO_BARS`, `MISSING_COLUMNS`, `NON_INTEGRAL_VOLUME`, … | From `HistoricalData` ([invariants](../domain-market-data.md#8-historicaldata)), e.g. Dukascopy files with no rows. |
