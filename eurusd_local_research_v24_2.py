#!/usr/bin/env python3
"""
EURUSD Local Research Builder v24.2
Same study as v24.1, built on the shared loader instead of its own copy.

v24.1 carried a private MT5 reader: separator sniffing, header detection,
headerless column layouts, per-file M1 -> M5 resampling, dedupe, source-file
selection. All of that now lives in `ports/data_file_access/` (parsing) and
`domain/` (processing), so this version deletes its copy and calls them:

    build_clean_dataset()  ->  the clean M5 frame + the numbers this report needs

What changed, beyond the deletion:
- Malformed source lines are counted and reported instead of vanishing silently.
- Sorting is stable, so "last file wins" is what actually happens where a month
  export, the next month's file and a yearly *_all.csv all claim one timestamp.
  v24.1's default quicksort picked an arbitrary row at those 12 boundaries.
- `--out` is its own path rather than a fixed directory inside `--folder`.
- `--clean-csv` skips the rebuild and studies an existing clean M5 file.

The research half -- the range/delay/stop/reward grid over the chronological
60/20/20 split -- is carried over unchanged, so a run on the same input
reproduces the v24.1 grid.

Run:
    python3 eurusd_local_research_v24_2.py --folder data/eurusd/1min

Optional:
    python3 eurusd_local_research_v24_2.py --clean-csv research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
    python3 eurusd_local_research_v24_2.py --session-open 10:00 --cutoff 14:00
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from domain.dataset import CleanDataset, build_clean_dataset

warnings.filterwarnings("ignore")

PIP = 0.0001
COST_PIPS = 1.7
DEFAULT_FOLDER = "data/eurusd/1min"
OUTDIR_NAME = "research_output_v24_2"
M5_NAME = "EURUSD_M5_CLEAN_2020_2026.csv"

RANGE_MINUTES = [30, 45, 60, 75, 90, 120]
ENTRY_DELAYS = [0, 5, 10, 15, 30]
STOP_FRACTIONS = [0.40, 0.50, 0.60, 0.67, 0.75]
R_MULTIPLES = [1.0, 1.5, 2.0, 2.5, 3.0]


def parse_hhmm(s):
    h, m = s.split(":")
    return int(h), int(m)


def data_quality_report(dataset: CleanDataset, outpath: Path) -> str:
    """The v24.1 data-quality report, written from the dataset's own counters."""
    lines = [
        "V24.2 DATA QUALITY REPORT",
        "=" * 90,
        f"Successful source files: {len(dataset.stats)}",
        f"Failed/skipped source files: {len(dataset.errors)}",
        f"Duplicate M5 timestamps removed: {dataset.duplicates_removed:,}",
        f"Final M5 candles: {len(dataset.frame):,}",
        f"First candle: {dataset.first}",
        f"Last candle: {dataset.last}",
        f"Clean M5 saved at: {outpath}",
    ]

    if dataset.skipped_lines:
        lines.append(f"Unparsable source lines skipped: {dataset.skipped_lines:,}")

    lines += ["", "FAILED/SKIPPED FILES", "-" * 90]
    lines += [f"{error.name} | {error.reason}" for error in dataset.errors]
    lines += ["", "SUCCESSFUL FILES", "-" * 90]
    lines += [
        f"{stat.name} | source {stat.source_rows:,} -> M5 {stat.output_rows:,}"
        f" | {stat.first} -> {stat.last}"
        + (f" | {stat.skipped_lines:,} lines skipped" if stat.skipped_lines else "")
        for stat in dataset.stats
    ]

    return "\n".join(lines)


def build_clean_m5(folder: Path, outdir: Path):
    """Stage 0: folder of raw M1 exports -> the clean M5 CSV + quality report."""
    dataset = build_clean_dataset(folder, rule="5min", progress=print)

    outpath = outdir / M5_NAME
    dataset.frame.to_csv(outpath, index=False)
    (outdir / "v24_2_data_quality.txt").write_text(
        data_quality_report(dataset, outpath), encoding="utf-8"
    )

    print("\nClean M5 created:")
    print(outpath)
    print(f"Candles: {len(dataset.frame):,}")
    print(f"Dates: {dataset.first} -> {dataset.last}")
    print(f"Duplicates removed: {dataset.duplicates_removed:,}")

    if dataset.skipped_lines:
        print(f"Unparsable lines skipped: {dataset.skipped_lines:,}")

    return dataset.frame


# ---------------------------------------------------------------------------
# Research half -- unchanged from v24.1.
# ---------------------------------------------------------------------------

def maxdd(vals):
    a = np.asarray(vals, float)
    if len(a) == 0:
        return np.nan
    eq = np.concatenate([[0.0], np.cumsum(a)])
    peak = np.maximum.accumulate(eq)
    return float(np.max(peak - eq))


def prep(df):
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
    x = x.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    x["date"] = x["datetime"].dt.date
    x["minute_of_day"] = x["datetime"].dt.hour * 60 + x["datetime"].dt.minute
    x["weekday"] = x["datetime"].dt.dayofweek
    return x[x["weekday"] < 5].copy()


def get_range(day, act, mins):
    g = day[(day["minute_of_day"] >= act - mins) & (day["minute_of_day"] < act)]
    if len(g) < max(mins // 5 - 1, 1):
        return None
    hi = float(g["high"].max())
    lo = float(g["low"].min())
    if hi <= lo:
        return None
    return hi, lo


def simulate(day, act, cutoff, rm, sf, rr):
    rg = get_range(day, act, rm)
    if rg is None:
        return None
    hi, lo = rg
    size = hi - lo
    le, se = hi, lo
    lsl = hi - sf * size
    ssl = lo + sf * size
    lr = (le - lsl) / PIP
    sr = (ssl - se) / PIP
    if lr <= 0 or sr <= 0:
        return None
    ltp = le + rr * (le - lsl)
    stp = se - rr * (ssl - se)

    w = day[(day["minute_of_day"] >= act) & (day["minute_of_day"] <= cutoff)]
    if w.empty:
        return None

    active = None
    result = 0.0
    trig = 0
    for _, b in w.iterrows():
        h = float(b["high"])
        l = float(b["low"])

        if active is None:
            up = h >= le
            dn = l <= se
            if up and dn:
                return {"ambiguous": 1}
            if up:
                active = "LONG"
                trig = 1
            elif dn:
                active = "SHORT"
                trig = 1
            continue

        if active == "LONG":
            hs = l <= lsl
            ht = h >= ltp
            if hs:
                result = -1.0 - COST_PIPS / lr
                active = None
                break
            if ht:
                result = rr - COST_PIPS / lr
                active = None
                break
        else:
            hs = h >= ssl
            ht = l <= stp
            if hs:
                result = -1.0 - COST_PIPS / sr
                active = None
                break
            if ht:
                result = rr - COST_PIPS / sr
                active = None
                break

    if active is not None:
        px = float(w.iloc[-1]["close"])
        if active == "LONG":
            result = ((px - le) / PIP) / lr - COST_PIPS / lr
        else:
            result = ((se - px) / PIP) / sr - COST_PIPS / sr

    return {"ambiguous": 0, "triggered": trig, "net_r": result}


def run_grid(df, oh, om, ch, cm, outdir):
    x = prep(df)
    openmin = oh * 60 + om
    cutoff = ch * 60 + cm

    days = sorted(x["date"].unique())
    a = int(len(days) * .60)
    b = int(len(days) * .80)
    disc = set(days[:a])
    val = set(days[a:b])
    test = set(days[b:])
    cache = {d: g.reset_index(drop=True) for d, g in x.groupby("date")}

    configs = [
        (rm, d, sf, rr)
        for rm in RANGE_MINUTES
        for d in ENTRY_DELAYS
        for sf in STOP_FRACTIONS
        for rr in R_MULTIPLES
    ]
    print(f"\nRunning {len(configs)} session configurations...")

    rows = []
    for i, (rm, delay, sf, rr) in enumerate(configs, 1):
        if i == 1 or i % 100 == 0:
            print(f"  config {i}/{len(configs)}")
        buckets = {"DISC": [], "VAL": [], "TEST": []}
        act = openmin + delay
        for d in days:
            r = simulate(cache[d], act, cutoff, rm, sf, rr)
            if r is None or r.get("ambiguous", 0):
                continue
            key = "DISC" if d in disc else "VAL" if d in val else "TEST"
            buckets[key].append(r)

        row = {"range_minutes": rm, "delay_minutes": delay, "stop_fraction": sf, "reward_r": rr}
        for k, arr in buckets.items():
            vals = [z["net_r"] for z in arr]
            trades = sum(z["triggered"] for z in arr)
            row[f"{k}_days"] = len(arr)
            row[f"{k}_trades"] = trades
            row[f"{k}_avg_r_day"] = np.mean(vals) if vals else np.nan
            row[f"{k}_total_r"] = np.sum(vals) if vals else np.nan
            row[f"{k}_prof_days"] = np.mean(np.array(vals) > 0) if vals else np.nan
            row[f"{k}_dd_r"] = maxdd(vals) if vals else np.nan

        row["ROBUST"] = bool(
            np.isfinite(row["DISC_avg_r_day"]) and
            np.isfinite(row["VAL_avg_r_day"]) and
            np.isfinite(row["TEST_avg_r_day"]) and
            row["DISC_avg_r_day"] > 0 and row["VAL_avg_r_day"] > 0 and row["TEST_avg_r_day"] > 0
        )
        rows.append(row)

    grid = pd.DataFrame(rows).sort_values(
        ["ROBUST", "TEST_avg_r_day", "VAL_avg_r_day", "DISC_avg_r_day"],
        ascending=[False, False, False, False]
    )
    grid.to_csv(outdir / "v24_2_range_grid.csv", index=False)

    rep = [
        "V24.2 MULTI-YEAR SESSION RANGE RESEARCH",
        "=" * 105,
        f"Broker-server session open tested: {oh:02d}:{om:02d}",
        f"Cutoff: {ch:02d}:{cm:02d}",
        f"Trading days: {len(days)}",
        f"Discovery / validation / final: {len(disc)} / {len(val)} / {len(test)}",
        f"Robust configurations: {int(grid['ROBUST'].sum())}",
        "",
        "TOP 30 CONFIGURATIONS",
        "-" * 105,
    ]

    for _, r in grid.head(30).iterrows():
        rep.append(
            f"{'ROBUST' if r['ROBUST'] else 'FAIL':<6} | "
            f"range {int(r['range_minutes']):3d}m | delay +{int(r['delay_minutes']):2d}m | "
            f"SL {r['stop_fraction']:.2f} | TP {r['reward_r']:.1f}R | "
            f"DISC {r['DISC_avg_r_day']:+.3f} | VAL {r['VAL_avg_r_day']:+.3f} | "
            f"TEST {r['TEST_avg_r_day']:+.3f} R/day | test trades {int(r['TEST_trades'])}"
        )

    (outdir / "v24_2_session_report.txt").write_text("\n".join(rep), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default=DEFAULT_FOLDER, help="folder of raw MT5 M1 exports")
    ap.add_argument("--out", default=OUTDIR_NAME, help="directory to write into")
    ap.add_argument("--clean-csv", default=None,
                    help="study this existing clean M5 CSV instead of rebuilding one")
    ap.add_argument("--session-open", default="10:00", help="BROKER SERVER TIME")
    ap.add_argument("--cutoff", default="14:00", help="BROKER SERVER TIME")
    args = ap.parse_args()

    outdir = Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    oh, om = parse_hhmm(args.session_open)
    ch, cm = parse_hhmm(args.cutoff)

    print("=" * 90)
    print("EURUSD LOCAL RESEARCH BUILDER v24.2")
    print("=" * 90)

    if args.clean_csv:
        clean = Path(args.clean_csv).resolve()
        print("Clean M5 source:", clean)
        m5 = pd.read_csv(clean)
        print(f"Candles: {len(m5):,}")
    else:
        folder = Path(args.folder).resolve()
        print("Source folder:", folder)
        m5 = build_clean_m5(folder, outdir)

    run_grid(m5, oh, om, ch, cm, outdir)

    print("\nDONE.")
    print("Open:", outdir)
    print("Read these text files:")
    if not args.clean_csv:
        print("  v24_2_data_quality.txt")
    print("  v24_2_session_report.txt")


if __name__ == "__main__":
    main()
