"""Tiny source files, one per format, for the loader tests.

Each writer produces 10 M1 bars starting at 2020-01-02 00:00: prices rise
0.0001 per bar, so M5 bar 0 is open 1.1000 / high 1.1006 / low 1.0998 /
close 1.1005.
"""

from pathlib import Path

import pandas as pd

START = pd.Timestamp("2020-01-02 00:00")


def _m1(n: int = 10) -> pd.DataFrame:
    base = [1.1000 + i * 0.0001 for i in range(n)]
    return pd.DataFrame({
        "datetime": pd.date_range(START, periods=n, freq="1min"),
        "open": base,
        "high": [b + 0.0002 for b in base],
        "low": [b - 0.0002 for b in base],
        "close": [b + 0.0001 for b in base],
        "tick_volume": [10] * n,
        "volume": [0] * n,
        "spread": [5] * n,  # points
    })


def write_mt5_export(path: Path, n: int = 10) -> Path:
    """A headerless, tab-separated MT5 M1 export."""
    frame = _m1(n)
    lines = [
        f"{r.datetime:%Y.%m.%d}\t{r.datetime:%H:%M}\t{r.open:.5f}\t{r.high:.5f}\t{r.low:.5f}\t"
        f"{r.close:.5f}\t{r.tick_volume}\t{r.volume}\t{r.spread}"
        for r in frame.itertuples()
    ]
    path.write_text("\n".join(lines) + "\n")
    return path


def write_dukascopy_month(folder: Path, n: int = 10, spread: float = 0.00002) -> Path:
    """A Dukascopy bid/ask pair for January 2020 (epoch-ms UTC timestamps)."""
    frame = _m1(n)
    stamps = (frame["datetime"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1ms")
    bid = pd.DataFrame({"timestamp": stamps, **{c: frame[c] for c in ("open", "high", "low", "close")}})
    ask = bid.assign(**{c: bid[c] + spread for c in ("open", "high", "low", "close")})
    bid.to_csv(folder / "eurusd-m1-bid-2020-01-01-2020-02-01.csv", index=False)
    ask.to_csv(folder / "eurusd-m1-ask-2020-01-01-2020-02-01.csv", index=False)
    return folder
