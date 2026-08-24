#!/usr/bin/env python3
"""
Candle DNA v26.1 — Narrow Asia Timing × Penetration × Volume Lab
================================================================

Purpose
-------
Fix the v26 timing bug and perform one focused reverse-engineering pass before
building an actual executable trade model.

v26 established a very stable base behavior on narrow-Asia days:

    first London break of Asia range -> Asia midpoint later reached ~60-62%

v26.1 asks whether that can be improved using ONLY:
    - correct breakout timing
    - breakout penetration
    - relative volume
    - close-back-inside vs close-outside behavior

No RSI, no Fibonacci, no large feature search.

IMPORTANT FIX
-------------
v26 accidentally stored absolute minute-of-day as "minutes_after_london".
v26.1 correctly stores:

    minutes_after_london = breakout_minute - london_open_minute

So:
    10:00 breakout -> 0
    10:05 breakout -> 5
    10:30 breakout -> 30

Input
-----
Use the clean local M5 dataset created by v24.1:

    research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv

Default broker-server times
---------------------------
Asia:        02:00 - 10:00
London open: 10:00
Study end:   14:00

Narrow Asia
-----------
Defined by the DISCOVERY-only Q1 Asia-range threshold, frozen for all splits.

Main outputs
------------
narrow_asia_v26_1_output/
    v26_1_report.txt
    v26_1_event_catalogue.csv
    v26_1_base_rates.csv
    v26_1_timing_buckets.csv
    v26_1_penetration_buckets.csv
    v26_1_volume_buckets.csv
    v26_1_close_behavior.csv
    v26_1_single_rules.csv
    v26_1_combo_rules.csv
    v26_1_stable_rules.csv
    v26_1_mae_profiles.csv

Hypothesis grid
---------------
Timing:
    <= 0m, 5m, 10m, 15m, 20m, 30m, 45m, 60m, 90m, 120m

Penetration max:
    <0.5, <1, <1.5, <2, <3, <5 pips

Penetration min:
    >=0.5, >=1, >=1.5, >=2, >=3 pips

Relative volume:
    >=1.0, 1.2, 1.4, 1.6, 1.8, 2.0

Close behavior:
    close back inside Asia
    close outside Asia

Combinations:
    timing + small penetration
    timing + volume
    small penetration + volume
    timing + small penetration + volume
    rejection + timing
    rejection + small penetration
    rejection + volume
    rejection + timing + small penetration
    rejection + timing + volume

Research standard
-----------------
60% discovery / 20% validation / 20% untouched final test.

A rule is marked STABLE only if:
    - enough samples in every split
    - midpoint reversion rate > split baseline in every split
    - split-to-split probability spread <= 10 percentage points

Run
---
python eurusd_narrow_asia_reversion_v26_1.py ^
  "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv"
"""

import argparse
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001

MIN_DISC = 60
MIN_VAL = 20
MIN_TEST = 20

TIME_MAX = [0, 5, 10, 15, 20, 30, 45, 60, 90, 120]
PEN_MAX = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0]
PEN_MIN = [0.5, 1.0, 1.5, 2.0, 3.0]
VOL_MIN = [1.0, 1.2, 1.4, 1.6, 1.8, 2.0]


def parse_hhmm(s):
    h, m = s.strip().split(":")
    return int(h), int(m)


def mod(h, m):
    return h * 60 + m


def load_data(path):
    df = pd.read_csv(path)

    required = {"datetime", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"]).copy()
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "tick_volume" in df.columns:
        df["volume_proxy"] = pd.to_numeric(df["tick_volume"], errors="coerce")
    elif "volume" in df.columns:
        df["volume_proxy"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume_proxy"] = np.nan

    df["date"] = df["datetime"].dt.date
    df["weekday"] = df["datetime"].dt.dayofweek
    df["minute_of_day"] = df["datetime"].dt.hour * 60 + df["datetime"].dt.minute

    df = df[df["weekday"] < 5].copy().reset_index(drop=True)

    pc = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)
    df["atr14_pips"] = tr.ewm(alpha=1/14, adjust=False).mean() / PIP

    vol_ma20 = df["volume_proxy"].rolling(20).mean()
    df["relvol20"] = np.where(
        vol_ma20 > 0,
        df["volume_proxy"] / vol_ma20,
        np.nan
    )

    return df


def split_dates(dates):
    dates = sorted(dates)
    n = len(dates)
    a = int(n * 0.60)
    b = int(n * 0.80)
    return set(dates[:a]), set(dates[a:b]), set(dates[b:])


def asia_stats(day, asia_start, asia_end):
    g = day[
        (day["minute_of_day"] >= asia_start)
        & (day["minute_of_day"] < asia_end)
    ]

    expected = max((asia_end - asia_start) // 5, 1)
    if len(g) < expected - 3:
        return None

    hi = float(g["high"].max())
    lo = float(g["low"].min())

    if not np.isfinite(hi) or not np.isfinite(lo) or hi <= lo:
        return None

    return {
        "high": hi,
        "low": lo,
        "mid": (hi + lo) / 2.0,
        "range_pips": (hi - lo) / PIP,
    }


def build_day_ranges(df, asia_start, asia_end):
    rows = []

    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)
        a = asia_stats(day, asia_start, asia_end)
        if a is None:
            continue

        rows.append({
            "date": date,
            "asia_range_pips": a["range_pips"],
        })

    return pd.DataFrame(rows)


def find_first_break(day, asia_hi, asia_lo, london_open, study_end):
    w = day[
        (day["minute_of_day"] >= london_open)
        & (day["minute_of_day"] <= study_end)
    ]

    for idx, r in w.iterrows():
        up = r["high"] >= asia_hi
        dn = r["low"] <= asia_lo

        if up and dn:
            return {"ambiguous": 1, "idx": idx, "side": "BOTH"}

        if up:
            return {"ambiguous": 0, "idx": idx, "side": "HIGH"}

        if dn:
            return {"ambiguous": 0, "idx": idx, "side": "LOW"}

    return None


def measure_event(day, idx, side, asia_hi, asia_lo, asia_mid, london_open, study_end):
    first = day.loc[idx]

    path = day.loc[idx:].copy()
    path = path[path["minute_of_day"] <= study_end]

    rng = asia_hi - asia_lo

    candle_range = float(first["high"] - first["low"])
    candle_body = abs(float(first["close"] - first["open"]))
    body_ratio = candle_body / candle_range if candle_range > 0 else 0.0

    mins_after = int(first["minute_of_day"]) - london_open

    out = {
        "minutes_after_london": mins_after,
        "penetration_pips": np.nan,
        "penetration_xrange": np.nan,
        "close_beyond_pips": np.nan,
        "closed_outside": 0,
        "close_back_inside": 0,
        "break_candle_range_pips": candle_range / PIP,
        "break_candle_body_pips": candle_body / PIP,
        "break_body_ratio": body_ratio,
        "break_relvol20": float(first["relvol20"]) if np.isfinite(first["relvol20"]) else np.nan,
        "break_atr14_pips": float(first["atr14_pips"]) if np.isfinite(first["atr14_pips"]) else np.nan,
        "midpoint_reached": 0,
        "opposite_side_reached": 0,
        "minutes_to_midpoint": np.nan,
        "max_extension_pips": np.nan,
        "max_extension_xrange": np.nan,
        "mae_before_midpoint_pips": np.nan,
        "mae_before_midpoint_xrange": np.nan,
    }

    if side == "HIGH":
        penetration = (float(first["high"]) - asia_hi) / PIP
        close_beyond = (float(first["close"]) - asia_hi) / PIP

        out["penetration_pips"] = penetration
        out["penetration_xrange"] = (
            (float(first["high"]) - asia_hi) / rng if rng > 0 else np.nan
        )
        out["close_beyond_pips"] = close_beyond
        out["closed_outside"] = int(first["close"] > asia_hi)
        out["close_back_inside"] = int(first["close"] < asia_hi)

        max_ext = (float(path["high"].max()) - asia_hi) / PIP
        out["max_extension_pips"] = max_ext
        out["max_extension_xrange"] = (
            (float(path["high"].max()) - asia_hi) / rng if rng > 0 else np.nan
        )

        mid_rows = path[path["low"] <= asia_mid]
        opp_rows = path[path["low"] <= asia_lo]

        if len(mid_rows):
            mid_idx = mid_rows.index[0]
            out["midpoint_reached"] = 1
            out["minutes_to_midpoint"] = (
                int(day.loc[mid_idx]["minute_of_day"]) - int(first["minute_of_day"])
            )
            pre_mid = day.loc[idx:mid_idx]
            mae = (float(pre_mid["high"].max()) - asia_hi) / PIP
            out["mae_before_midpoint_pips"] = mae
            out["mae_before_midpoint_xrange"] = (
                (float(pre_mid["high"].max()) - asia_hi) / rng if rng > 0 else np.nan
            )
        else:
            out["mae_before_midpoint_pips"] = max_ext
            out["mae_before_midpoint_xrange"] = out["max_extension_xrange"]

        out["opposite_side_reached"] = int(len(opp_rows) > 0)

    else:
        penetration = (asia_lo - float(first["low"])) / PIP
        close_beyond = (asia_lo - float(first["close"])) / PIP

        out["penetration_pips"] = penetration
        out["penetration_xrange"] = (
            (asia_lo - float(first["low"])) / rng if rng > 0 else np.nan
        )
        out["close_beyond_pips"] = close_beyond
        out["closed_outside"] = int(first["close"] < asia_lo)
        out["close_back_inside"] = int(first["close"] > asia_lo)

        max_ext = (asia_lo - float(path["low"].min())) / PIP
        out["max_extension_pips"] = max_ext
        out["max_extension_xrange"] = (
            (asia_lo - float(path["low"].min())) / rng if rng > 0 else np.nan
        )

        mid_rows = path[path["high"] >= asia_mid]
        opp_rows = path[path["high"] >= asia_hi]

        if len(mid_rows):
            mid_idx = mid_rows.index[0]
            out["midpoint_reached"] = 1
            out["minutes_to_midpoint"] = (
                int(day.loc[mid_idx]["minute_of_day"]) - int(first["minute_of_day"])
            )
            pre_mid = day.loc[idx:mid_idx]
            mae = (asia_lo - float(pre_mid["low"].min())) / PIP
            out["mae_before_midpoint_pips"] = mae
            out["mae_before_midpoint_xrange"] = (
                (asia_lo - float(pre_mid["low"].min())) / rng if rng > 0 else np.nan
            )
        else:
            out["mae_before_midpoint_pips"] = max_ext
            out["mae_before_midpoint_xrange"] = out["max_extension_xrange"]

        out["opposite_side_reached"] = int(len(opp_rows) > 0)

    return out


def build_catalogue(df, narrow_threshold, asia_start, asia_end, london_open, study_end):
    rows = []

    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)

        a = asia_stats(day, asia_start, asia_end)
        if a is None or a["range_pips"] > narrow_threshold:
            continue

        info = find_first_break(
            day,
            a["high"],
            a["low"],
            london_open,
            study_end
        )

        if info is None or info["ambiguous"]:
            continue

        m = measure_event(
            day,
            info["idx"],
            info["side"],
            a["high"],
            a["low"],
            a["mid"],
            london_open,
            study_end
        )

        rows.append({
            "date": date,
            "weekday": day.iloc[0]["datetime"].day_name(),
            "asia_high": a["high"],
            "asia_low": a["low"],
            "asia_mid": a["mid"],
            "asia_range_pips": a["range_pips"],
            "break_side": info["side"],
            **m,
        })

    return pd.DataFrame(rows)


def add_split(df, disc, val, test):
    out = df.copy()

    def f(d):
        if d in disc:
            return "DISC"
        if d in val:
            return "VAL"
        if d in test:
            return "TEST"
        return "OTHER"

    out["split"] = out["date"].map(f)
    return out


def profile_table(cat, col, bins, labels):
    x = cat.copy()
    x["_bucket"] = pd.cut(
        x[col],
        bins=bins,
        labels=labels,
        right=False
    )

    rows = []

    for split in ["DISC", "VAL", "TEST"]:
        g = x[x["split"] == split]

        for bucket, h in g.groupby("_bucket", observed=True):
            if len(h) == 0:
                continue

            rows.append({
                "split": split,
                "bucket": str(bucket),
                "samples": len(h),
                "midpoint_rate": h["midpoint_reached"].mean(),
                "opposite_rate": h["opposite_side_reached"].mean(),
                "median_mae_pips": h["mae_before_midpoint_pips"].median(),
                "median_penetration_pips": h["penetration_pips"].median(),
                "median_relvol": h["break_relvol20"].median(),
            })

    return pd.DataFrame(rows)


def make_rule(name, fn):
    return {"name": name, "fn": fn}


def build_rules():
    rules = []

    # Singles.
    for t in TIME_MAX:
        rules.append(make_rule(
            f"break <= {t}m",
            lambda d, t=t: d["minutes_after_london"] <= t
        ))

    for p in PEN_MAX:
        rules.append(make_rule(
            f"penetration < {p:.1f}p",
            lambda d, p=p: d["penetration_pips"] < p
        ))

    for p in PEN_MIN:
        rules.append(make_rule(
            f"penetration >= {p:.1f}p",
            lambda d, p=p: d["penetration_pips"] >= p
        ))

    for rv in VOL_MIN:
        rules.append(make_rule(
            f"relvol >= {rv:.1f}",
            lambda d, rv=rv: d["break_relvol20"] >= rv
        ))

    rules.append(make_rule(
        "close back inside",
        lambda d: d["close_back_inside"] == 1
    ))
    rules.append(make_rule(
        "close outside",
        lambda d: d["closed_outside"] == 1
    ))

    # Timing + small penetration.
    for t in [5,10,15,20,30,45,60]:
        for p in [0.5,1.0,1.5,2.0,3.0]:
            rules.append(make_rule(
                f"break<={t}m + pen<{p:.1f}p",
                lambda d, t=t, p=p:
                    (d["minutes_after_london"] <= t)
                    & (d["penetration_pips"] < p)
            ))

    # Timing + volume.
    for t in [5,10,15,20,30,45,60]:
        for rv in [1.2,1.4,1.6,1.8]:
            rules.append(make_rule(
                f"break<={t}m + relvol>={rv:.1f}",
                lambda d, t=t, rv=rv:
                    (d["minutes_after_london"] <= t)
                    & (d["break_relvol20"] >= rv)
            ))

    # Small penetration + volume.
    for p in [1.0,1.5,2.0,3.0]:
        for rv in [1.2,1.4,1.6,1.8]:
            rules.append(make_rule(
                f"pen<{p:.1f}p + relvol>={rv:.1f}",
                lambda d, p=p, rv=rv:
                    (d["penetration_pips"] < p)
                    & (d["break_relvol20"] >= rv)
            ))

    # Triple combo.
    for t in [10,15,20,30,45]:
        for p in [1.0,1.5,2.0]:
            for rv in [1.2,1.4,1.6]:
                rules.append(make_rule(
                    f"break<={t}m + pen<{p:.1f}p + relvol>={rv:.1f}",
                    lambda d, t=t, p=p, rv=rv:
                        (d["minutes_after_london"] <= t)
                        & (d["penetration_pips"] < p)
                        & (d["break_relvol20"] >= rv)
                ))

    # Rejection-specific.
    for t in [5,10,15,20,30,45,60]:
        rules.append(make_rule(
            f"REJECT + break<={t}m",
            lambda d, t=t:
                (d["close_back_inside"] == 1)
                & (d["minutes_after_london"] <= t)
        ))

    for p in [0.5,1.0,1.5,2.0,3.0]:
        rules.append(make_rule(
            f"REJECT + pen<{p:.1f}p",
            lambda d, p=p:
                (d["close_back_inside"] == 1)
                & (d["penetration_pips"] < p)
        ))

    for rv in [1.2,1.4,1.6,1.8]:
        rules.append(make_rule(
            f"REJECT + relvol>={rv:.1f}",
            lambda d, rv=rv:
                (d["close_back_inside"] == 1)
                & (d["break_relvol20"] >= rv)
        ))

    for t in [10,15,20,30,45]:
        for p in [1.0,1.5,2.0]:
            rules.append(make_rule(
                f"REJECT + break<={t}m + pen<{p:.1f}p",
                lambda d, t=t, p=p:
                    (d["close_back_inside"] == 1)
                    & (d["minutes_after_london"] <= t)
                    & (d["penetration_pips"] < p)
            ))

    for t in [10,15,20,30,45]:
        for rv in [1.2,1.4,1.6]:
            rules.append(make_rule(
                f"REJECT + break<={t}m + relvol>={rv:.1f}",
                lambda d, t=t, rv=rv:
                    (d["close_back_inside"] == 1)
                    & (d["minutes_after_london"] <= t)
                    & (d["break_relvol20"] >= rv)
            ))

    return rules


def evaluate_rules(cat):
    base = {
        split: cat[cat["split"] == split]["midpoint_reached"].mean()
        for split in ["DISC","VAL","TEST"]
    }

    rows = []

    for rule in build_rules():
        stats = {}

        for split in ["DISC","VAL","TEST"]:
            g = cat[cat["split"] == split]
            h = g[rule["fn"](g)]

            n = len(h)
            rate = h["midpoint_reached"].mean() if n else np.nan
            lift = rate / base[split] if n and base[split] > 0 else np.nan

            stats[split] = {
                "n": n,
                "rate": rate,
                "lift": lift,
                "median_mae": h["mae_before_midpoint_pips"].median() if n else np.nan,
            }

        d = stats["DISC"]
        v = stats["VAL"]
        t = stats["TEST"]

        spread = np.nan
        avg_rate = np.nan
        stable = False

        if all(np.isfinite(x["rate"]) for x in [d,v,t]):
            spread = max(d["rate"],v["rate"],t["rate"]) - min(d["rate"],v["rate"],t["rate"])
            avg_rate = np.mean([d["rate"],v["rate"],t["rate"]])

            stable = (
                d["n"] >= MIN_DISC
                and v["n"] >= MIN_VAL
                and t["n"] >= MIN_TEST
                and d["lift"] > 1.0
                and v["lift"] > 1.0
                and t["lift"] > 1.0
                and spread <= 0.10
            )

        rows.append({
            "rule": rule["name"],
            "DISC_n": d["n"],
            "DISC_rate": d["rate"],
            "DISC_lift": d["lift"],
            "DISC_median_mae": d["median_mae"],
            "VAL_n": v["n"],
            "VAL_rate": v["rate"],
            "VAL_lift": v["lift"],
            "VAL_median_mae": v["median_mae"],
            "TEST_n": t["n"],
            "TEST_rate": t["rate"],
            "TEST_lift": t["lift"],
            "TEST_median_mae": t["median_mae"],
            "avg_rate": avg_rate,
            "split_spread": spread,
            "stable": stable,
        })

    all_rules = pd.DataFrame(rows)

    single_mask = ~all_rules["rule"].str.contains(r"\+")
    singles = all_rules[single_mask].copy()
    combos = all_rules[~single_mask].copy()

    stable = all_rules[
        (all_rules["stable"] == True)
    ].copy()

    if len(stable):
        stable["score"] = (
            stable["avg_rate"]
            - stable["split_spread"]
            + 0.02*np.log10(stable["TEST_n"].clip(lower=1))
        )
        stable = stable.sort_values(
            ["score","TEST_rate","TEST_n"],
            ascending=[False,False,False]
        )

    singles = singles.sort_values(
        ["stable","TEST_lift","TEST_n"],
        ascending=[False,False,False]
    )
    combos = combos.sort_values(
        ["stable","TEST_lift","TEST_n"],
        ascending=[False,False,False]
    )

    return singles, combos, stable, base


def close_behavior_table(cat):
    rows = []

    for split in ["DISC","VAL","TEST"]:
        g = cat[cat["split"] == split]

        for label, mask in [
            ("close_back_inside", g["close_back_inside"] == 1),
            ("closed_outside", g["closed_outside"] == 1),
        ]:
            h = g[mask]
            if len(h):
                rows.append({
                    "split": split,
                    "behavior": label,
                    "samples": len(h),
                    "midpoint_rate": h["midpoint_reached"].mean(),
                    "opposite_rate": h["opposite_side_reached"].mean(),
                    "median_mae_pips": h["mae_before_midpoint_pips"].median(),
                    "median_penetration_pips": h["penetration_pips"].median(),
                    "median_relvol": h["break_relvol20"].median(),
                })

    return pd.DataFrame(rows)


def mae_profiles(cat):
    rows = []

    for split in ["DISC","VAL","TEST"]:
        for outcome in [0,1]:
            g = cat[
                (cat["split"] == split)
                & (cat["midpoint_reached"] == outcome)
            ]

            x = g["mae_before_midpoint_pips"].dropna()
            if not len(x):
                continue

            rows.append({
                "split": split,
                "midpoint_reached": outcome,
                "samples": len(x),
                "median": x.median(),
                "p75": x.quantile(.75),
                "p90": x.quantile(.90),
                "p95": x.quantile(.95),
            })

    return pd.DataFrame(rows)


def write_report(outdir, threshold, cat, base, timing, pen, vol, close_df, stable, mae):
    report = []

    report.append("CANDLE DNA v26.1 — NARROW ASIA TIMING × PENETRATION × VOLUME LAB")
    report.append("="*122)
    report.append("")
    report.append(f"Frozen narrow-Asia threshold: <= {threshold:.2f} pips")
    report.append(f"Usable events: {len(cat)}")
    report.append("")

    report.append("BASE MIDPOINT REVERSION")
    report.append("-"*122)

    for split in ["DISC","VAL","TEST"]:
        g = cat[cat["split"] == split]
        report.append(
            f"{split:<5} | midpoint {base[split]*100:5.1f}% | "
            f"n={len(g)} | opposite {g['opposite_side_reached'].mean()*100:5.1f}%"
        )

    report.append("")
    report.append("CORRECTED TEST BREAK-TIMING BUCKETS")
    report.append("-"*122)

    for _, r in timing[timing["split"]=="TEST"].iterrows():
        report.append(
            f"{r['bucket']:<8} | n={int(r['samples']):>3} | "
            f"midpoint {r['midpoint_rate']*100:5.1f}% | "
            f"opp {r['opposite_rate']*100:5.1f}% | "
            f"MAE med {r['median_mae_pips']:.2f}p | "
            f"pen med {r['median_penetration_pips']:.2f}p"
        )

    report.append("")
    report.append("TEST PENETRATION BUCKETS")
    report.append("-"*122)

    for _, r in pen[pen["split"]=="TEST"].iterrows():
        report.append(
            f"{r['bucket']:<8} | n={int(r['samples']):>3} | "
            f"midpoint {r['midpoint_rate']*100:5.1f}% | "
            f"opp {r['opposite_rate']*100:5.1f}% | "
            f"MAE med {r['median_mae_pips']:.2f}p | "
            f"relvol med {r['median_relvol']:.2f}"
        )

    report.append("")
    report.append("TEST RELATIVE-VOLUME BUCKETS")
    report.append("-"*122)

    for _, r in vol[vol["split"]=="TEST"].iterrows():
        report.append(
            f"{r['bucket']:<8} | n={int(r['samples']):>3} | "
            f"midpoint {r['midpoint_rate']*100:5.1f}% | "
            f"opp {r['opposite_rate']*100:5.1f}% | "
            f"MAE med {r['median_mae_pips']:.2f}p"
        )

    report.append("")
    report.append("CLOSE BEHAVIOR")
    report.append("-"*122)

    for _, r in close_df.iterrows():
        report.append(
            f"{r['split']:<5} | {r['behavior']:<17} | n={int(r['samples']):>3} | "
            f"midpoint {r['midpoint_rate']*100:5.1f}% | "
            f"opp {r['opposite_rate']*100:5.1f}% | "
            f"MAE med {r['median_mae_pips']:.2f}p"
        )

    report.append("")
    report.append("BEST STABLE RULES")
    report.append("-"*122)

    if stable.empty:
        report.append("No rule met all sample / lift / stability requirements.")
    else:
        for _, r in stable.head(40).iterrows():
            report.append(
                f"STABLE | "
                f"DISC {r['DISC_rate']*100:5.1f}% n={int(r['DISC_n']):>3} "
                f"({r['DISC_lift']:.2f}x) | "
                f"VAL {r['VAL_rate']*100:5.1f}% n={int(r['VAL_n']):>3} "
                f"({r['VAL_lift']:.2f}x) | "
                f"TEST {r['TEST_rate']*100:5.1f}% n={int(r['TEST_n']):>3} "
                f"({r['TEST_lift']:.2f}x) | "
                f"TEST MAE med {r['TEST_median_mae']:.2f}p | "
                f"{r['rule']}"
            )

    report.append("")
    report.append("MAE PROFILE")
    report.append("-"*122)

    for _, r in mae.iterrows():
        label = "REVERTED" if int(r["midpoint_reached"]) == 1 else "FAILED"
        report.append(
            f"{r['split']:<5} {label:<8} | n={int(r['samples']):>3} | "
            f"median {r['median']:.2f}p | "
            f"P75 {r['p75']:.2f}p | P90 {r['p90']:.2f}p | P95 {r['p95']:.2f}p"
        )

    report.append("")
    report.append("NEXT DECISION")
    report.append("-"*122)
    report.append(
        "If a timing × penetration × volume or rejection rule reaches roughly 70%+ with adequate samples "
        "and stays stable across all three splits, v27 should convert that exact rule into an executable fade."
    )
    report.append(
        "If the best stable subset remains only mid-60s, v27 should still test expectancy because a midpoint target "
        "can be much larger than a carefully chosen structural stop."
    )

    (outdir/"v26_1_report.txt").write_text("\n".join(report), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="narrow_asia_v26_1_output")
    ap.add_argument("--asia-start", default="02:00")
    ap.add_argument("--asia-end", default="10:00")
    ap.add_argument("--london-open", default="10:00")
    ap.add_argument("--study-end", default="14:00")
    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    ah, am = parse_hhmm(args.asia_start)
    aeh, aem = parse_hhmm(args.asia_end)
    lh, lm = parse_hhmm(args.london_open)
    sh, sm = parse_hhmm(args.study_end)

    asia_start = mod(ah, am)
    asia_end = mod(aeh, aem)
    london_open = mod(lh, lm)
    study_end = mod(sh, sm)

    print("="*122)
    print("CANDLE DNA v26.1 — NARROW ASIA TIMING × PENETRATION × VOLUME LAB")
    print("="*122)
    print("Loading:", args.csv)

    df = load_data(args.csv)

    day_ranges = build_day_ranges(df, asia_start, asia_end)
    dates = sorted(day_ranges["date"].unique())
    disc_dates, val_dates, test_dates = split_dates(dates)

    disc_ranges = day_ranges[
        day_ranges["date"].isin(disc_dates)
    ]["asia_range_pips"].dropna()

    threshold = float(disc_ranges.quantile(0.25))

    print(f"Frozen discovery-Q1 narrow threshold: <= {threshold:.2f} pips")

    cat = build_catalogue(
        df,
        threshold,
        asia_start,
        asia_end,
        london_open,
        study_end
    )

    cat = add_split(cat, disc_dates, val_dates, test_dates)

    print(
        f"Events: {len(cat)} | "
        f"DISC {(cat['split']=='DISC').sum()} | "
        f"VAL {(cat['split']=='VAL').sum()} | "
        f"TEST {(cat['split']=='TEST').sum()}"
    )

    # Corrected timing buckets.
    timing = profile_table(
        cat,
        "minutes_after_london",
        bins=[-np.inf,1,6,11,16,21,31,46,61,91,121,np.inf],
        labels=["0m","1-5m","6-10m","11-15m","16-20m","21-30m","31-45m","46-60m","61-90m","91-120m","120m+"]
    )

    penetration = profile_table(
        cat,
        "penetration_pips",
        bins=[-np.inf,0.5,1,1.5,2,3,5,8,np.inf],
        labels=["<0.5","0.5-1","1-1.5","1.5-2","2-3","3-5","5-8","8+"]
    )

    volume = profile_table(
        cat,
        "break_relvol20",
        bins=[-np.inf,1.0,1.2,1.4,1.6,1.8,2.0,2.5,3.0,np.inf],
        labels=["<1.0","1.0-1.2","1.2-1.4","1.4-1.6","1.6-1.8","1.8-2.0","2.0-2.5","2.5-3.0","3.0+"]
    )

    singles, combos, stable, base = evaluate_rules(cat)
    close_df = close_behavior_table(cat)
    mae = mae_profiles(cat)

    base_df = pd.DataFrame([
        {
            "split": s,
            "samples": int((cat["split"]==s).sum()),
            "midpoint_rate": base[s],
            "opposite_rate": cat[cat["split"]==s]["opposite_side_reached"].mean(),
        }
        for s in ["DISC","VAL","TEST"]
    ])

    cat.to_csv(outdir/"v26_1_event_catalogue.csv", index=False)
    base_df.to_csv(outdir/"v26_1_base_rates.csv", index=False)
    timing.to_csv(outdir/"v26_1_timing_buckets.csv", index=False)
    penetration.to_csv(outdir/"v26_1_penetration_buckets.csv", index=False)
    volume.to_csv(outdir/"v26_1_volume_buckets.csv", index=False)
    close_df.to_csv(outdir/"v26_1_close_behavior.csv", index=False)
    singles.to_csv(outdir/"v26_1_single_rules.csv", index=False)
    combos.to_csv(outdir/"v26_1_combo_rules.csv", index=False)
    stable.to_csv(outdir/"v26_1_stable_rules.csv", index=False)
    mae.to_csv(outdir/"v26_1_mae_profiles.csv", index=False)

    write_report(
        outdir,
        threshold,
        cat,
        base,
        timing,
        penetration,
        volume,
        close_df,
        stable,
        mae
    )

    print("\n" + "="*122)
    print("V26.1 COMPLETE")
    print("="*122)
    print("Output folder:", outdir.resolve())
    print("\nPaste v26_1_report.txt here.")


if __name__ == "__main__":
    main()
