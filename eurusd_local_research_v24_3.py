#!/usr/bin/env python3
"""
EURUSD Local Research Builder v24.3
Same research grid as v24.2, but it studies the pre-built M5 export directly
instead of rebuilding M5 from raw M1 on every run.

v24.2 pointed stage 0 at `data/eurusd/1min` and did the whole M1 -> M5 build
itself (via `build_clean_dataset`). v24.3 assumes stage 0 already ran -- the
merged M5 file `data/eurusd/5min/EURUSD_M5.csv` that `resample_csv.py` produces --
and consumes it.

It still calls `build_clean_dataset()`, deliberately: given a folder whose files
are already on the M5 grid, `resample_ohlc(frame, "M5")` is an identity op
(verified: `frame.equals(resampled)`), so the use case reduces to exactly the
parts v24.3 wants -- source-file selection with the generated-file skip list,
per-file sort + dedup, stable-sort "last file wins" merge across files, and the
per-file counters the data-quality report is built from. Nothing in
`application/` or the ports changed; only this script's input did.

Trade-off vs v24.2: faster, and no duplicated M1->M5 logic, but v24.3 now
depends on stage 0 having been run (`data/eurusd/5min/EURUSD_M5.csv` must exist
and be current). v24.2 stays as the self-contained rebuild-from-M1 path.

Run:
    python3 resample_csv.py --source data/eurusd/1min --destination data/eurusd/5min/EURUSD.csv --timeframe M5
    python3 eurusd_local_research_v24_3.py --folder data/eurusd/5min

Optional:
    python3 eurusd_local_research_v24_3.py --clean-csv output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
    python3 eurusd_local_research_v24_3.py --session-open 10:00 --cutoff 14:00
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from application.build_clean_dataset_use_case import CleanDataset, build_clean_dataset

warnings.filterwarnings("ignore")

PIP = 0.0001
COST_PIPS = 1.7

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
        "V24.3 DATA QUALITY REPORT",
        "=" * 90,
        f"Successful source files: {len(dataset.stats)}",
        f"Failed/skipped source files: {len(dataset.errors)}",
        f"Duplicate M5 timestamps removed: {dataset.duplicates_removed_count:,}",
        f"Final M5 candles: {len(dataset.frame):,}",
        f"First candle: {dataset.start_dt}",
        f"Last candle: {dataset.end_dt}",
        f"Clean M5 saved at: {outpath}",
    ]

    if dataset.skipped_lines_count:
        lines.append(f"Unparsable source lines skipped: {dataset.skipped_lines_count:,}")

    lines += ["", "FAILED/SKIPPED FILES", "-" * 90]
    lines += [f"{error.name} | {error.reason}" for error in dataset.errors]
    lines += ["", "SUCCESSFUL FILES", "-" * 90]
    lines += [
        f"{stat.name} | source {stat.source_rows_count:,} -> M5 {stat.output_rows_count:,}"
        f" | {stat.first} -> {stat.last}"
        + (f" | {stat.skipped_lines_count:,} lines skipped" if stat.skipped_lines_count else "")
        for stat in dataset.stats
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Research half -- unchanged from v24.1 / v24.2.
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
    grid.to_csv(outdir / "v24_3_range_grid.csv", index=False)

    rep = [
        "V24.3 MULTI-YEAR SESSION RANGE RESEARCH",
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

    (outdir / "v24_3_session_report.txt").write_text("\n".join(rep), encoding="utf-8")


def parse_args():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--out",
        default="output/research_output_v24_3",
        help="directory to write into")

    ap.add_argument(
        "--clean-csv",
        default="data/eurusd/5min/EURUSD_M5.csv",
        help="study this existing clean M5 CSV")

    ap.add_argument(
        "--session-open",
        default="10:00",
        help="BROKER SERVER TIME")

    ap.add_argument(
        "--cutoff",
        default="14:00",
        help="BROKER SERVER TIME")

    args = ap.parse_args()

    return args


def main():
    args = parse_args()

    outdir = Path(args.out).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    oh, om = parse_hhmm(args.session_open)
    ch, cm = parse_hhmm(args.cutoff)

    print("=" * 90)
    print("EURUSD LOCAL RESEARCH BUILDER v24.3")
    print("=" * 90)

    if args.clean_csv:
        clean = Path(args.clean_csv).resolve()
        print("Clean M5 source:", clean)
        #m5 = pd.read_csv(clean)
        dataset = build_clean_dataset(clean, progress=print)
        m5 = dataset.frame
        print(f"Candles: {len(m5):,}")

    run_grid(m5, oh, om, ch, cm, outdir)

    print("\nDONE.")
    print("Open:", outdir)
    print("Read these text files:")
    print("  v24_3_session_report.txt")


if __name__ == "__main__":
    main()
