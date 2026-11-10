# Domain: Indicators

The RSI and the RSI divergence detection, used by the [`rsi_divergence` plugin](plugins.md#7-rsi_divergence-rsidivergence) and the [ScanRsiDivergences use case](use-cases.md#7-scanrsidivergences). Pure calculations over a bar table. Types and rules are in [conventions.md](conventions.md).

## Contents

1. [RSI](#1-rsi)
2. [Divergence](#2-divergence)
3. [Divergence entries](#3-divergence-entries)

---

## 1. RSI

*Python: `domain/pandas_approach/rsi.py`.* Wilder's Relative Strength Index, matching TradingView Pine's `ta.rsi`.

### `rsi(close: List<Float>, length: Integer = 14) -> List<Float?>`

1. `delta[i] = close[i] − close[i − 1]`; `delta[0]` is null.
2. `gain[i] = max(delta[i], 0)`, `loss[i] = max(−delta[i], 0)`.
3. Smooth each with Wilder's average `A` (below), giving `avg_gain` and `avg_loss`.
4. `rs = avg_gain / avg_loss`; `rsi = 100 − 100 / (1 + rs)`. So `avg_loss = 0` gives 100, and both zero gives NaN.

Wilder's average of `x` (`x[0]` is the null from step 1):

- `A[i]` is null for `i < length`.
- `A[length] = mean(x[1 … length])`, the simple average of the first `length` usable values.
- `A[i] = (A[i − 1] × (length − 1) + x[i]) / length` for `i > length`.
- With `length` values or fewer, everything is null.

Seeding with the simple average matters: an exponential average seeded from the first value disagrees by up to ~30 RSI points for the first few hundred bars.

---

## 2. Divergence

*Python: `domain/pandas_approach/divergence.py`.* A translation of the LuxAlgo-style regular/hidden divergence indicator (`temp/RSI Divergence Indicator.pine`).

### Category (Enum)

`REGULAR` (`Regular`), `HIDDEN` (`Hidden`).

### Direction (Enum)

`BULLISH` (`Bullish`), `BEARISH` (`Bearish`).

### Divergence

| Property | Type | Notes |
|---|---|---|
| `category` | `Category` | |
| `direction` | `Direction` | |
| `start_time` | `LocalDateTime` | the older pivot bar |
| `end_time` | `LocalDateTime` | the newer pivot bar |
| `start_value` | `Float` | oscillator at the older pivot |
| `end_value` | `Float` | oscillator at the newer pivot |

### `find_divergences(table, oscillator: List<Float?>, pivot_left = 5, pivot_right = 5, range_lower = 5, range_upper = 60, include_hidden = false) -> List<Divergence>`

`table` needs `datetime`, `high` and `low`, row-aligned with `oscillator`.

1. **Pivots** of the oscillator, for every index `p` with `pivot_left <= p < n − pivot_right`:
   - pivot **high**: every one of the `pivot_left` values before it is `<` it, and every one of the `pivot_right` values after it is `<=` it;
   - pivot **low**: every value before is `>` it, every value after is `>=` it.

   A comparison with a null is false, so a null is never a pivot and blocks its neighbours. (This is Pine's `ta.pivothigh`/`ta.pivotlow`.)
2. **Pairs.** Take each pair of **consecutive** pivots of the same kind, `(prev, curr)`, and keep it only when `range_lower <= curr − prev <= range_upper` (in bars). A pair out of range is skipped, but `curr` is still the `prev` of the next pair.
3. **Bullish**, from pivot lows (price = `low`):
   - price lower low (`low[curr] < low[prev]`) and oscillator higher low (`osc[curr] > osc[prev]`) → Regular Bullish;
   - otherwise, only with `include_hidden`: price higher low and oscillator lower low → Hidden Bullish.
4. **Bearish**, from pivot highs (price = `high`):
   - price higher high and oscillator lower high → Regular Bearish;
   - otherwise, only with `include_hidden`: price lower high and oscillator higher high → Hidden Bearish.
5. Return the bullish list followed by the bearish one, stable-sorted by `end_time`.

A pivot is only knowable `pivot_right` bars after it (it needs the bars to its right). Using a divergence before then is look-ahead.

### `filter_regular_by_band(divergences, lower: Float, upper: Float) -> List<Divergence>`

Keeps every hidden divergence, and a regular one only when its `start_value` is **outside** `[lower, upper]` and its `end_value` **inside** it: the oscillator leaving overbought/oversold territory.

---

## 3. Divergence entries

*Python: `domain/pandas_approach/divergence_positions.py`.*

### DivergencePosition

An entry signal tied to the divergence that produced it, with no exit levels yet.

| Property | Type |
|---|---|
| `divergence` | `Divergence` |
| `side` | `Side` |
| `open_time` | `LocalDateTime` |
| `open_price` | `Float` |

### `open_positions(table, divergences, pivot_right: Integer, rsi_lower: Float, rsi_upper: Float) -> List<DivergencePosition>`

For each divergence, in order:

1. Skip hidden divergences.
2. Side: `LONG` if `start_value < rsi_lower`, `SHORT` if `start_value > rsi_upper`, otherwise skip.
3. Entry bar = the row of `end_time` (the newer pivot) + `pivot_right` + 1: the first bar after the pivot is confirmed. Skip if that is past the last row.
4. `open_time` and `open_price` are that bar's `datetime` and `open`.
