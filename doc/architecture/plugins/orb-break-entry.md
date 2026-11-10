# `orb_break_entry`: OrbBreakEntry

A [plugin](README.md) of the [application blueprint](../README.md).

*Python: `strategies/orb_break_entry.py`. Rules: `doc/strategies/orb-break-entry/`.* Stop orders at both sides of the opening range.

Parameters: those of [OpeningRangeStrategy](opening-range-strategy.md), with `risk_reward` = **2.0**.

## Steps

For each opening range (`H`, `L`, `M`, order window, `exit_dt`), two independent stop orders; each fills at most once and they don't cancel each other, so a date has 0–2 trades (one bar through both levels opens both):

| Field | Long order | Short order |
|---|---|---|
| fills on | the first window bar with `high >= H` | the first window bar with `low <= L` |
| `side` | `LONG` | `SHORT` |
| `open_price` | `H` | `L` |
| `sl` | `M` | `M` |
| `tp` | `H + risk_reward × abs(H − M)` | `L − risk_reward × abs(L − M)` |
| `tag` | `break-high` | `break-low` |
| `open_dt` | the fill bar's `datetime` | |
| `entry_fill` | `AT_LEVEL` (SL/TP checked from the next bar: it can't see a stop hit on the fill bar, a slight optimism) | |
| `exit_dt` | the range's `exit_dt` | |

Fills are at the level even when a bar gaps through it.
