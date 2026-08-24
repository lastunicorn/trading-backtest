#!/usr/bin/env python3
"""
Candle DNA v26 — Narrow Asia London Sweep / Midpoint Reversion Lab
=================================================================

Purpose
-------
v25 found a stable behavior:

    On narrow-Asia days, London almost always expands the Asia range,
    and after the first Asia-range break, price returns to the Asia midpoint
    materially more often than it reaches the opposite side.

v26 focuses ONLY on that behavior.

We are NOT optimizing a complete trading strategy yet.

We are reverse-engineering the trajectory AFTER the first London break of the
Asian range on narrow-Asia days.

Main questions
--------------
1) How far beyond the Asia high/low does price usually travel before midpoint reversion?
2) What observable breakout behaviors distinguish midpoint-reversion days from non-reversion days?
3) Does a close back inside Asia materially increase midpoint-reversion probability?
4) Does penetration size matter?
5) Does breakout timing matter?
6) Does relative volume / candle strength matter?
7) Can we identify a stable subset with materially higher midpoint-reversion probability?
8) What does adverse excursion look like before midpoint is reached?

Input
-----
Use the clean local M5 dataset created by v24.1:

    research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv

Default broker-server windows
-----------------------------
Asia:         02:00 - 10:00
London open:  10:00
Study end:    14:00

These are BROKER SERVER TIME and are configurable.

Narrow Asia definition
----------------------
Default:
    bottom quartile (Q1) of Asia range size

IMPORTANT:
To reduce leakage, v26 calculates the narrow-range threshold FROM DISCOVERY DAYS ONLY,
then freezes that threshold for validation and final test.

Example:
    if discovery Q1 threshold = 21.4 pips,
    then "narrow Asia" means Asia range <= 21.4 pips
    in discovery, validation, AND final test.

Breakout event
--------------
For each narrow-Asia day:

    - freeze Asia high / low / midpoint
    - wait from London open
    - identify FIRST Asia boundary break
    - exclude ambiguous 5m bars that touch both Asia high and Asia low
    - follow the trajectory until study end

Measured trajectory
-------------------
- first break side
- breakout time
- penetration on breakout bar
- maximum extension beyond Asia edge
- extension in Asia-range multiples
- breakout candle range / body / body ratio
- close beyond boundary
- close back inside range
- relative volume 20
- ATR14
- minutes to midpoint
- midpoint reached yes/no
- opposite side reached yes/no
- maximum favorable movement toward midpoint
- maximum adverse extension before midpoint
- adverse excursion in pips
- adverse excursion as Asia-range multiple

Explicit hypotheses tested
--------------------------
A) Close back inside Asia after first break
B) Breakout candle closes outside Asia
C) Penetration thresholds:
       >= 0.5 / 1 / 2 / 3 / 5 / 8 pips
D) Penetration relative to Asia range:
       >= 0.05x / 0.10x / 0.15x / 0.20x / 0.25x
E) Break timing:
       by +0 / +5 / +10 / +15 / +30 / +60 minutes
F) Relative volume:
       >= 1.0 / 1.2 / 1.4 / 1.6 / 2.0
G) Break candle body ratio:
       >= 0.40 / 0.60 / 0.75
H) Weak breakout / rejection:
       close_back_inside + penetration threshold combinations
I) Strong breakout continuation:
       close_outside + body strength + volume combinations

Chronological methodology
-------------------------
60% discovery
20% validation
20% untouched final test

Rule thresholds are explicit and hypothesis-driven.
No arbitrary ML model is used.

A candidate is only interesting if:
    - adequate sample in all 3 splits
    - midpoint-reversion probability is elevated in discovery
    - remains elevated in validation
    - remains elevated in final test
    - behavior is reasonably stable across splits

Outputs
-------
narrow_asia_v26_output/
    v26_report.txt
    v26_event_catalogue.csv
    v26_base_rates.csv
    v26_feature_summary.csv
    v26_rule_discovery.csv
    v26_rule_validation.csv
    v26_rule_final.csv
    v26_stable_rules.csv
    v26_adverse_excursion.csv
    v26_penetration_buckets.csv
    v26_timing_buckets.csv

Run
---
python eurusd_narrow_asia_reversion_v26.py ^
  "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv"

Optional:
python eurusd_narrow_asia_reversion_v26.py ^
  "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv" ^
  --asia-start 02:00 --asia-end 10:00 --london-open 10:00 --study-end 14:00
"""

import argparse
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001

MIN_DISC = 80
MIN_VAL = 25
MIN_TEST = 25

PEN_PIPS = [0.5, 1.0, 2.0, 3.0, 5.0, 8.0]
PEN_X = [0.05, 0.10, 0.15, 0.20, 0.25]
TIME_LIMITS = [0, 5, 10, 15, 30, 60]
RELVOL_LEVELS = [1.0, 1.2, 1.4, 1.6, 2.0]
BODY_LEVELS = [0.40, 0.60, 0.75]


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

    # ATR14 on M5.
    pc = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - pc).abs(),
        (df["low"] - pc).abs(),
    ], axis=1).max(axis=1)
    df["atr14_pips"] = tr.ewm(alpha=1/14, adjust=False).mean() / PIP

    # Relative tick volume.
    volma = df["volume_proxy"].rolling(20).mean()
    df["relvol20"] = np.where(volma > 0, df["volume_proxy"] / volma, np.nan)

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

    # tolerate a few missing bars
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
        s = asia_stats(day, asia_start, asia_end)
        if s is None:
            continue

        rows.append({
            "date": date,
            "asia_range_pips": s["range_pips"],
        })

    return pd.DataFrame(rows)


def first_break(day, asia_hi, asia_lo, london_open, study_end):
    w = day[
        (day["minute_of_day"] >= london_open)
        & (day["minute_of_day"] <= study_end)
    ]

    for idx, r in w.iterrows():
        up = r["high"] >= asia_hi
        dn = r["low"] <= asia_lo

        if up and dn:
            return {
                "ambiguous": 1,
                "idx": idx,
                "side": "BOTH"
            }

        if up:
            return {
                "ambiguous": 0,
                "idx": idx,
                "side": "HIGH"
            }

        if dn:
            return {
                "ambiguous": 0,
                "idx": idx,
                "side": "LOW"
            }

    return None


def trajectory(day, idx, side, asia_hi, asia_lo, asia_mid, study_end):
    first = day.loc[idx]
    path = day.loc[idx:].copy()
    path = path[path["minute_of_day"] <= study_end]

    rng = asia_hi - asia_lo

    candle_range = float(first["high"] - first["low"])
    candle_body = abs(float(first["close"] - first["open"]))
    body_ratio = candle_body / candle_range if candle_range > 0 else 0.0

    result = {
        "minutes_after_london": np.nan,
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

    result["minutes_after_london"] = int(first["minute_of_day"])

    if side == "HIGH":
        penetration = (float(first["high"]) - asia_hi) / PIP
        close_beyond = (float(first["close"]) - asia_hi) / PIP
        result["penetration_pips"] = penetration
        result["penetration_xrange"] = ((float(first["high"]) - asia_hi) / rng) if rng > 0 else np.nan
        result["close_beyond_pips"] = close_beyond
        result["closed_outside"] = int(first["close"] > asia_hi)
        result["close_back_inside"] = int(first["close"] < asia_hi)

        max_ext = (float(path["high"].max()) - asia_hi) / PIP
        result["max_extension_pips"] = max_ext
        result["max_extension_xrange"] = ((float(path["high"].max()) - asia_hi) / rng) if rng > 0 else np.nan

        mid_rows = path[path["low"] <= asia_mid]
        opp_rows = path[path["low"] <= asia_lo]

        if len(mid_rows):
            mid_idx = mid_rows.index[0]
            result["midpoint_reached"] = 1
            result["minutes_to_midpoint"] = int(day.loc[mid_idx]["minute_of_day"]) - int(first["minute_of_day"])

            pre_mid = day.loc[idx:mid_idx]
            mae = (float(pre_mid["high"].max()) - asia_hi) / PIP
            result["mae_before_midpoint_pips"] = mae
            result["mae_before_midpoint_xrange"] = ((float(pre_mid["high"].max()) - asia_hi) / rng) if rng > 0 else np.nan
        else:
            result["mae_before_midpoint_pips"] = max_ext
            result["mae_before_midpoint_xrange"] = result["max_extension_xrange"]

        result["opposite_side_reached"] = int(len(opp_rows) > 0)

    elif side == "LOW":
        penetration = (asia_lo - float(first["low"])) / PIP
        close_beyond = (asia_lo - float(first["close"])) / PIP
        result["penetration_pips"] = penetration
        result["penetration_xrange"] = ((asia_lo - float(first["low"])) / rng) if rng > 0 else np.nan
        result["close_beyond_pips"] = close_beyond
        result["closed_outside"] = int(first["close"] < asia_lo)
        result["close_back_inside"] = int(first["close"] > asia_lo)

        max_ext = (asia_lo - float(path["low"].min())) / PIP
        result["max_extension_pips"] = max_ext
        result["max_extension_xrange"] = ((asia_lo - float(path["low"].min())) / rng) if rng > 0 else np.nan

        mid_rows = path[path["high"] >= asia_mid]
        opp_rows = path[path["high"] >= asia_hi]

        if len(mid_rows):
            mid_idx = mid_rows.index[0]
            result["midpoint_reached"] = 1
            result["minutes_to_midpoint"] = int(day.loc[mid_idx]["minute_of_day"]) - int(first["minute_of_day"])

            pre_mid = day.loc[idx:mid_idx]
            mae = (asia_lo - float(pre_mid["low"].min())) / PIP
            result["mae_before_midpoint_pips"] = mae
            result["mae_before_midpoint_xrange"] = ((asia_lo - float(pre_mid["low"].min())) / rng) if rng > 0 else np.nan
        else:
            result["mae_before_midpoint_pips"] = max_ext
            result["mae_before_midpoint_xrange"] = result["max_extension_xrange"]

        result["opposite_side_reached"] = int(len(opp_rows) > 0)

    return result


def build_event_catalogue(df, narrow_threshold, asia_start, asia_end, london_open, study_end):
    rows = []

    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)

        a = asia_stats(day, asia_start, asia_end)
        if a is None:
            continue

        if a["range_pips"] > narrow_threshold:
            continue

        info = first_break(
            day,
            a["high"],
            a["low"],
            london_open,
            study_end
        )

        if info is None or info["ambiguous"]:
            continue

        t = trajectory(
            day,
            info["idx"],
            info["side"],
            a["high"],
            a["low"],
            a["mid"],
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
            **t
        })

    return pd.DataFrame(rows)


def add_split(cat, disc, val, test):
    out = cat.copy()

    def label(d):
        if d in disc:
            return "DISC"
        if d in val:
            return "VAL"
        if d in test:
            return "TEST"
        return "OTHER"

    out["split"] = out["date"].map(label)
    return out


def feature_summary(cat):
    num = [
        "asia_range_pips",
        "penetration_pips",
        "penetration_xrange",
        "close_beyond_pips",
        "break_candle_range_pips",
        "break_candle_body_pips",
        "break_body_ratio",
        "break_relvol20",
        "break_atr14_pips",
        "max_extension_pips",
        "max_extension_xrange",
        "mae_before_midpoint_pips",
        "mae_before_midpoint_xrange",
        "minutes_to_midpoint",
    ]

    rows = []

    for split in ["DISC", "VAL", "TEST"]:
        g = cat[cat["split"] == split]

        for outcome in [0, 1]:
            h = g[g["midpoint_reached"] == outcome]

            for f in num:
                x = h[f].replace([np.inf, -np.inf], np.nan).dropna()
                if len(x) == 0:
                    continue

                rows.append({
                    "split": split,
                    "midpoint_reached": outcome,
                    "feature": f,
                    "samples": len(x),
                    "mean": x.mean(),
                    "median": x.median(),
                    "p25": x.quantile(0.25),
                    "p75": x.quantile(0.75),
                })

    return pd.DataFrame(rows)


def make_rule(name, mask_fn):
    return {"name": name, "mask_fn": mask_fn}


def rule_library():
    rules = []

    rules.append(make_rule(
        "Break candle closes back inside Asia",
        lambda d: d["close_back_inside"] == 1
    ))
    rules.append(make_rule(
        "Break candle closes outside Asia",
        lambda d: d["closed_outside"] == 1
    ))

    for p in PEN_PIPS:
        rules.append(make_rule(
            f"Penetration >= {p:.1f} pips",
            lambda d, p=p: d["penetration_pips"] >= p
        ))
        rules.append(make_rule(
            f"Penetration < {p:.1f} pips",
            lambda d, p=p: d["penetration_pips"] < p
        ))

        rules.append(make_rule(
            f"Close back inside + penetration >= {p:.1f}p",
            lambda d, p=p: (d["close_back_inside"] == 1) & (d["penetration_pips"] >= p)
        ))

    for x in PEN_X:
        rules.append(make_rule(
            f"Penetration >= {x:.2f}x Asia range",
            lambda d, x=x: d["penetration_xrange"] >= x
        ))
        rules.append(make_rule(
            f"Close back inside + penetration >= {x:.2f}x Asia",
            lambda d, x=x: (d["close_back_inside"] == 1) & (d["penetration_xrange"] >= x)
        ))

    for t in TIME_LIMITS:
        rules.append(make_rule(
            f"First break by +{t} minutes",
            lambda d, t=t: d["minutes_after_london"] <= t
        ))
        rules.append(make_rule(
            f"Close back inside + break by +{t}m",
            lambda d, t=t: (d["close_back_inside"] == 1) & (d["minutes_after_london"] <= t)
        ))

    for rv in RELVOL_LEVELS:
        rules.append(make_rule(
            f"Relative volume >= {rv:.1f}",
            lambda d, rv=rv: d["break_relvol20"] >= rv
        ))
        rules.append(make_rule(
            f"Close back inside + relvol >= {rv:.1f}",
            lambda d, rv=rv: (d["close_back_inside"] == 1) & (d["break_relvol20"] >= rv)
        ))

    for b in BODY_LEVELS:
        rules.append(make_rule(
            f"Break body ratio >= {b:.2f}",
            lambda d, b=b: d["break_body_ratio"] >= b
        ))
        rules.append(make_rule(
            f"Close outside + body ratio >= {b:.2f}",
            lambda d, b=b: (d["closed_outside"] == 1) & (d["break_body_ratio"] >= b)
        ))

    # Hypothesis combinations directly inspired by v25/v22.
    for p in [1.0, 2.0, 3.0, 5.0]:
        for t in [5, 10, 15, 30]:
            rules.append(make_rule(
                f"REJECTION: close back inside + pen>={p:.1f}p + by {t}m",
                lambda d, p=p, t=t:
                    (d["close_back_inside"] == 1)
                    & (d["penetration_pips"] >= p)
                    & (d["minutes_after_london"] <= t)
            ))

    for p in [1.0, 2.0, 3.0]:
        for rv in [1.2, 1.4, 1.6]:
            rules.append(make_rule(
                f"REJECTION: close inside + pen>={p:.1f}p + relvol>={rv:.1f}",
                lambda d, p=p, rv=rv:
                    (d["close_back_inside"] == 1)
                    & (d["penetration_pips"] >= p)
                    & (d["break_relvol20"] >= rv)
            ))

    for p in [1.0, 2.0, 3.0]:
        for rv in [1.2, 1.4, 1.6]:
            rules.append(make_rule(
                f"CONTINUATION: close outside + pen>={p:.1f}p + relvol>={rv:.1f}",
                lambda d, p=p, rv=rv:
                    (d["closed_outside"] == 1)
                    & (d["penetration_pips"] >= p)
                    & (d["break_relvol20"] >= rv)
            ))

    return rules


def evaluate_rules(cat):
    base_by_split = {
        split: cat[cat["split"] == split]["midpoint_reached"].mean()
        for split in ["DISC", "VAL", "TEST"]
    }

    rules = rule_library()
    discovery_rows = []
    validation_rows = []
    final_rows = []
    stable_rows = []

    for rule in rules:
        split_stats = {}

        for split in ["DISC", "VAL", "TEST"]:
            g = cat[cat["split"] == split]
            mask = rule["mask_fn"](g)
            h = g[mask]

            n = len(h)
            rate = h["midpoint_reached"].mean() if n else np.nan
            base = base_by_split[split]

            split_stats[split] = {
                "samples": n,
                "rate": rate,
                "base": base,
                "lift": rate / base if n and base > 0 else np.nan,
            }

        d = split_stats["DISC"]
        v = split_stats["VAL"]
        t = split_stats["TEST"]

        discovery_rows.append({
            "rule": rule["name"],
            "samples": d["samples"],
            "rate": d["rate"],
            "base": d["base"],
            "lift": d["lift"],
        })

        if d["samples"] >= MIN_DISC:
            validation_rows.append({
                "rule": rule["name"],
                "DISC_samples": d["samples"],
                "DISC_rate": d["rate"],
                "DISC_lift": d["lift"],
                "VAL_samples": v["samples"],
                "VAL_rate": v["rate"],
                "VAL_lift": v["lift"],
            })

        if d["samples"] >= MIN_DISC and v["samples"] >= MIN_VAL:
            final_rows.append({
                "rule": rule["name"],
                "DISC_samples": d["samples"],
                "DISC_rate": d["rate"],
                "DISC_lift": d["lift"],
                "VAL_samples": v["samples"],
                "VAL_rate": v["rate"],
                "VAL_lift": v["lift"],
                "TEST_samples": t["samples"],
                "TEST_rate": t["rate"],
                "TEST_lift": t["lift"],
            })

        if (
            d["samples"] >= MIN_DISC
            and v["samples"] >= MIN_VAL
            and t["samples"] >= MIN_TEST
            and np.isfinite(d["rate"])
            and np.isfinite(v["rate"])
            and np.isfinite(t["rate"])
        ):
            spread = max(d["rate"], v["rate"], t["rate"]) - min(d["rate"], v["rate"], t["rate"])
            avg = np.mean([d["rate"], v["rate"], t["rate"]])

            # Stable midpoint-reversion subset:
            # positive lift in all 3 splits and <=10 percentage-point spread.
            stable = (
                d["lift"] > 1.0
                and v["lift"] > 1.0
                and t["lift"] > 1.0
                and spread <= 0.10
            )

            stable_rows.append({
                "rule": rule["name"],
                "DISC_n": d["samples"],
                "DISC_rate": d["rate"],
                "DISC_lift": d["lift"],
                "VAL_n": v["samples"],
                "VAL_rate": v["rate"],
                "VAL_lift": v["lift"],
                "TEST_n": t["samples"],
                "TEST_rate": t["rate"],
                "TEST_lift": t["lift"],
                "avg_rate": avg,
                "split_spread": spread,
                "stable": stable,
            })

    disc = pd.DataFrame(discovery_rows).sort_values(
        ["lift", "samples"], ascending=[False, False]
    )

    val = pd.DataFrame(validation_rows)
    if len(val):
        val = val.sort_values(
            ["VAL_lift", "VAL_samples"], ascending=[False, False]
        )

    final = pd.DataFrame(final_rows)
    if len(final):
        final = final.sort_values(
            ["TEST_lift", "TEST_samples"], ascending=[False, False]
        )

    stable = pd.DataFrame(stable_rows)
    if len(stable):
        stable["score"] = stable["avg_rate"] - stable["split_spread"]
        stable = stable.sort_values(
            ["stable", "score", "TEST_n"],
            ascending=[False, False, False]
        )

    return disc, val, final, stable, base_by_split


def penetration_buckets(cat):
    bins = [-np.inf, 0.5, 1, 2, 3, 5, 8, np.inf]
    labels = ["<0.5","0.5-1","1-2","2-3","3-5","5-8","8+"]

    x = cat.copy()
    x["penetration_bucket"] = pd.cut(
        x["penetration_pips"], bins=bins, labels=labels, right=False
    )

    rows = []

    for split in ["DISC", "VAL", "TEST"]:
        g = x[x["split"] == split]
        for bucket, h in g.groupby("penetration_bucket", observed=True):
            if len(h) == 0:
                continue

            rows.append({
                "split": split,
                "penetration_bucket": str(bucket),
                "samples": len(h),
                "midpoint_rate": h["midpoint_reached"].mean(),
                "opposite_rate": h["opposite_side_reached"].mean(),
                "median_mae_pips": h["mae_before_midpoint_pips"].median(),
                "median_max_extension_pips": h["max_extension_pips"].median(),
            })

    return pd.DataFrame(rows)


def timing_buckets(cat):
    bins = [-np.inf, 1, 6, 11, 16, 31, 61, np.inf]
    labels = ["0m","1-5m","6-10m","11-15m","16-30m","31-60m","60m+"]

    x = cat.copy()
    x["timing_bucket"] = pd.cut(
        x["minutes_after_london"], bins=bins, labels=labels, right=False
    )

    rows = []

    for split in ["DISC", "VAL", "TEST"]:
        g = x[x["split"] == split]
        for bucket, h in g.groupby("timing_bucket", observed=True):
            if len(h) == 0:
                continue

            rows.append({
                "split": split,
                "timing_bucket": str(bucket),
                "samples": len(h),
                "midpoint_rate": h["midpoint_reached"].mean(),
                "opposite_rate": h["opposite_side_reached"].mean(),
                "median_penetration_pips": h["penetration_pips"].median(),
            })

    return pd.DataFrame(rows)


def adverse_excursion_table(cat):
    rows = []

    for split in ["DISC", "VAL", "TEST"]:
        for outcome in [0, 1]:
            g = cat[
                (cat["split"] == split)
                & (cat["midpoint_reached"] == outcome)
            ]

            x = g["mae_before_midpoint_pips"].dropna()

            if len(x) == 0:
                continue

            rows.append({
                "split": split,
                "midpoint_reached": outcome,
                "samples": len(x),
                "mean_mae_pips": x.mean(),
                "median_mae_pips": x.median(),
                "p75_mae_pips": x.quantile(0.75),
                "p90_mae_pips": x.quantile(0.90),
                "p95_mae_pips": x.quantile(0.95),
            })

    return pd.DataFrame(rows)


def write_report(outdir, threshold, cat, base, stable, pen, timing, adverse):
    report = []

    report.append("CANDLE DNA v26 — NARROW ASIA LONDON SWEEP / MIDPOINT REVERSION LAB")
    report.append("="*118)
    report.append("")
    report.append(f"Frozen narrow-Asia threshold from DISCOVERY Q1: <= {threshold:.2f} pips")
    report.append(f"Usable narrow-Asia first-break events: {len(cat)}")
    report.append("")

    report.append("BASE MIDPOINT-REVERSION RATE")
    report.append("-"*118)

    for split in ["DISC","VAL","TEST"]:
        g = cat[cat["split"] == split]
        report.append(
            f"{split:<5} | midpoint reached {base[split]*100:5.1f}% | "
            f"n={len(g)} | opposite side {g['opposite_side_reached'].mean()*100:5.1f}%"
        )

    report.append("")
    report.append("BEST STABLE RULES")
    report.append("-"*118)

    if stable.empty:
        report.append("No rule met all sample/stability requirements.")
    else:
        for _, r in stable.head(35).iterrows():
            report.append(
                f"{'STABLE' if r['stable'] else 'UNSTABLE':<8} | "
                f"DISC {r['DISC_rate']*100:5.1f}% n={int(r['DISC_n']):>3} "
                f"({r['DISC_lift']:.2f}x) | "
                f"VAL {r['VAL_rate']*100:5.1f}% n={int(r['VAL_n']):>3} "
                f"({r['VAL_lift']:.2f}x) | "
                f"TEST {r['TEST_rate']*100:5.1f}% n={int(r['TEST_n']):>3} "
                f"({r['TEST_lift']:.2f}x) | "
                f"{r['rule']}"
            )

    report.append("")
    report.append("TEST PENETRATION BUCKETS")
    report.append("-"*118)

    if len(pen):
        for _, r in pen[pen["split"]=="TEST"].iterrows():
            report.append(
                f"{r['penetration_bucket']:<7} | n={int(r['samples']):>3} | "
                f"midpoint {r['midpoint_rate']*100:5.1f}% | "
                f"opposite {r['opposite_rate']*100:5.1f}% | "
                f"median MAE {r['median_mae_pips']:.2f}p"
            )

    report.append("")
    report.append("TEST BREAK-TIMING BUCKETS")
    report.append("-"*118)

    if len(timing):
        for _, r in timing[timing["split"]=="TEST"].iterrows():
            report.append(
                f"{r['timing_bucket']:<7} | n={int(r['samples']):>3} | "
                f"midpoint {r['midpoint_rate']*100:5.1f}% | "
                f"opposite {r['opposite_rate']*100:5.1f}% | "
                f"median penetration {r['median_penetration_pips']:.2f}p"
            )

    report.append("")
    report.append("ADVERSE EXCURSION BEFORE MIDPOINT")
    report.append("-"*118)

    if len(adverse):
        for _, r in adverse.iterrows():
            label = "REVERTED" if int(r["midpoint_reached"]) == 1 else "FAILED"
            report.append(
                f"{r['split']:<5} {label:<8} | n={int(r['samples']):>3} | "
                f"median {r['median_mae_pips']:.2f}p | "
                f"P75 {r['p75_mae_pips']:.2f}p | "
                f"P90 {r['p90_mae_pips']:.2f}p | "
                f"P95 {r['p95_mae_pips']:.2f}p"
            )

    report.append("")
    report.append("WHAT V26 IS TRYING TO FIND")
    report.append("-"*118)
    report.append(
        "The useful result is a stable rule that meaningfully lifts midpoint-reversion probability "
        "above the narrow-Asia baseline AND leaves a manageable adverse-excursion distribution."
    )
    report.append(
        "If one exists, v27 can convert that exact behavior into an executable fade setup with entry, stop, "
        "midpoint target, costs, and chronological expectancy."
    )
    report.append(
        "If no stable subset exists, the 60-65% narrow-Asia midpoint behavior is real but may not be precise "
        "enough for a tradeable entry trigger."
    )

    (outdir/"v26_report.txt").write_text("\n".join(report), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Clean M5 CSV from v24.1")
    ap.add_argument("--out", default="narrow_asia_v26_output")
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

    asia_start = mod(ah,am)
    asia_end = mod(aeh,aem)
    london_open = mod(lh,lm)
    study_end = mod(sh,sm)

    print("="*118)
    print("CANDLE DNA v26 — NARROW ASIA LONDON SWEEP / MIDPOINT REVERSION LAB")
    print("="*118)
    print("Loading:", args.csv)

    df = load_data(args.csv)

    print(f"M5 candles: {len(df):,}")
    print(f"First: {df['datetime'].min()}")
    print(f"Last:  {df['datetime'].max()}")

    day_ranges = build_day_ranges(df, asia_start, asia_end)
    dates = sorted(day_ranges["date"].unique())
    disc_dates, val_dates, test_dates = split_dates(dates)

    # Discovery-only frozen Q1 threshold.
    disc_ranges = day_ranges[day_ranges["date"].isin(disc_dates)]["asia_range_pips"].dropna()
    narrow_threshold = float(disc_ranges.quantile(0.25))

    print(f"Discovery Q1 narrow-Asia threshold: <= {narrow_threshold:.2f} pips")

    cat = build_event_catalogue(
        df,
        narrow_threshold,
        asia_start,
        asia_end,
        london_open,
        study_end
    )

    cat = add_split(cat, disc_dates, val_dates, test_dates)

    print(
        f"Narrow-Asia first-break events: {len(cat)} | "
        f"DISC {(cat['split']=='DISC').sum()} | "
        f"VAL {(cat['split']=='VAL').sum()} | "
        f"TEST {(cat['split']=='TEST').sum()}"
    )

    feature_df = feature_summary(cat)

    disc_rules, val_rules, final_rules, stable_rules, base = evaluate_rules(cat)

    pen_df = penetration_buckets(cat)
    timing_df = timing_buckets(cat)
    adverse_df = adverse_excursion_table(cat)

    base_df = pd.DataFrame([
        {
            "split": split,
            "samples": int((cat["split"]==split).sum()),
            "midpoint_rate": base[split],
            "opposite_rate": cat[cat["split"]==split]["opposite_side_reached"].mean(),
            "close_back_inside_rate": cat[cat["split"]==split]["close_back_inside"].mean(),
        }
        for split in ["DISC","VAL","TEST"]
    ])

    cat.to_csv(outdir/"v26_event_catalogue.csv", index=False)
    base_df.to_csv(outdir/"v26_base_rates.csv", index=False)
    feature_df.to_csv(outdir/"v26_feature_summary.csv", index=False)
    disc_rules.to_csv(outdir/"v26_rule_discovery.csv", index=False)
    val_rules.to_csv(outdir/"v26_rule_validation.csv", index=False)
    final_rules.to_csv(outdir/"v26_rule_final.csv", index=False)
    stable_rules.to_csv(outdir/"v26_stable_rules.csv", index=False)
    adverse_df.to_csv(outdir/"v26_adverse_excursion.csv", index=False)
    pen_df.to_csv(outdir/"v26_penetration_buckets.csv", index=False)
    timing_df.to_csv(outdir/"v26_timing_buckets.csv", index=False)

    write_report(
        outdir,
        narrow_threshold,
        cat,
        base,
        stable_rules,
        pen_df,
        timing_df,
        adverse_df
    )

    print("\n" + "="*118)
    print("V26 COMPLETE")
    print("="*118)
    print("Output folder:", outdir.resolve())
    print("\nPaste v26_report.txt here.")
    print("If v26 finds a stable high-probability reversion subset, v27 will turn it into an actual trade model.")


if __name__ == "__main__":
    main()
