# `orb_retest_entry`: OrbRetestEntry

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/orb_retest_entry.py`. Rules: `doc/strategies/orb-retest-entry/`.* After the first break of the opening range, a limit order at its midpoint.

Parameters: those of [OpeningRangeStrategy](opening-range-strategy.md), with `risk_reward` = **3.0**.

## Steps

For each opening range (`H`, `L`, `M`, order window, `exit_dt`):

1. **Break:** the first window bar with `high >= H` (upside) or `low <= L` (downside). None: skip. Both on one bar: skip.
2. **Fill:** from the bar **after** the break to the window's end, the first bar reaching `M`: `low <= M` after an upside break, `high >= M` after a downside one. None: skip. So a date has 0–1 trades. (The break bar can't fill: OHLC can't say whether it reached `M` before or after the break.)

| Field | After an upside break | After a downside break |
|---|---|---|
| `side` | `LONG` | `SHORT` |
| `open_price` | `M` | `M` |
| `sl` | `L` | `H` |
| `tp` | `M + risk_reward × abs(M − L)` | `M − risk_reward × abs(M − H)` |
| `tag` | `retest-high` | `retest-low` |
| `open_dt` | the fill bar's `datetime` | |
| `entry_fill` | `AT_LEVEL` | |
| `exit_dt` | the range's `exit_dt` | |

`AT_LEVEL` makes it optimistic: price reaches `M` before the stop beyond it, so a fill bar that also reached the stop was stopped out, but the simulator doesn't check the fill bar.
