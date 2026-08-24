#!/usr/bin/env python3
"""
Candle DNA v25 — EURUSD Multi-Year Behavior Atlas
=================================================

Purpose
-------
Stop trying to optimize a strategy first.

Use the clean multi-year EURUSD M5 dataset to answer:

    "What does EURUSD do with surprising consistency?"

This script studies repeatable session / structural behaviors and reports them
chronologically across:

    60% discovery
    20% validation
    20% untouched final test

It does NOT optimize entries, stops, or take-profits.

Default session times are BROKER SERVER TIME and are fully configurable.

Typical run
-----------
From the EURUSD_Data folder:

    python eurusd_behavior_atlas_v25.py ^
      "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv"

If your broker chart shows London open at 10:00 and New York open at 15:30:

    python eurusd_behavior_atlas_v25.py ^
      "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv" ^
      --london-open 10:00 --ny-open 15:30

Outputs
-------
behavior_atlas_v25_output/
    v25_report.txt
    v25_daily_atlas.csv
    v25_session_summary.csv
    v25_asia_sweep_behaviors.csv
    v25_previous_day_behaviors.csv
    v25_impulse_behaviors.csv
    v25_high_low_timing.csv
    v25_regime_behaviors.csv
    v25_candidate_behaviors.csv

What is measured
----------------
Daily/session:
- Asia range
- pre-London 60m / 120m range
- London first-hour range and direction
- London 4-hour range and direction
- NY first-hour range and direction
- full-day range / direction
- high-of-day time
- low-of-day time

Asia range behavior after London open:
- which side of Asia breaks first
- whether both sides are eventually taken
- whether opposite side is reached after first sweep
- whether midpoint is reached after first sweep
- whether first break closes back inside Asia
- extension after first break in pips and Asia-range multiples

Previous-day structure:
- PDH / PDL first interaction
- whether both PDH and PDL are touched
- whether PDH/PDL sweep rejects back inside
- continuation after PDH/PDL break

Impulse behavior after London open:
- first 5 / 10 / 15 / 20 pip directional impulse
- whether it extends another 50%
- whether it retraces 50%
- which happens first

Regimes:
- Asia range quartiles
- daily ATR regime
- weekday
- narrow vs wide overnight conditions

Research standard
-----------------
The useful behaviors are NOT merely high percentages.
They should:
- have adequate sample size
- appear in discovery
- remain similar in validation
- remain similar in final test

This is a behavior-discovery tool, not a backtest.
"""

import argparse
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001

IMPULSE_PIPS = [5, 10, 15, 20]
EXTEND_MULT = 0.50
RETRACE_MULT = 0.50

MIN_DISC = 100
MIN_VAL = 30
MIN_TEST = 30


def parse_hhmm(s):
    h, m = s.strip().split(":")
    return int(h), int(m)


def minute_of_day(h, m):
    return h * 60 + m


def between_wrap(series, start, end):
    """
    Boolean mask for a minute-of-day interval.
    Supports intervals crossing midnight.
    """
    if start <= end:
        return (series >= start) & (series < end)
    return (series >= start) | (series < end)


def load_data(path):
    df = pd.read_csv(path)

    required = {"datetime", "open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime", "open", "high", "low", "close"]).copy()
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["date"] = df["datetime"].dt.date
    df["weekday"] = df["datetime"].dt.dayofweek
    df["minute_of_day"] = df["datetime"].dt.hour * 60 + df["datetime"].dt.minute

    return df[df["weekday"] < 5].copy().reset_index(drop=True)


def split_dates(dates):
    dates = sorted(dates)
    n = len(dates)
    a = int(n * 0.60)
    b = int(n * 0.80)
    return set(dates[:a]), set(dates[a:b]), set(dates[b:])


def session_stats(g):
    if g.empty:
        return {
            "open": np.nan, "high": np.nan, "low": np.nan, "close": np.nan,
            "range_pips": np.nan, "net_pips": np.nan
        }

    o = float(g.iloc[0]["open"])
    h = float(g["high"].max())
    l = float(g["low"].min())
    c = float(g.iloc[-1]["close"])

    return {
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "range_pips": (h - l) / PIP,
        "net_pips": (c - o) / PIP,
    }


def first_touch_after(g, start_minute, level_hi, level_lo, end_minute=None):
    """
    Returns first side touched after start:
    HIGH / LOW / BOTH / NONE, plus row index and time.
    """
    w = g[g["minute_of_day"] >= start_minute].copy()
    if end_minute is not None:
        w = w[w["minute_of_day"] <= end_minute]

    for idx, r in w.iterrows():
        up = r["high"] >= level_hi
        dn = r["low"] <= level_lo

        if up and dn:
            return "BOTH", idx, int(r["minute_of_day"])
        if up:
            return "HIGH", idx, int(r["minute_of_day"])
        if dn:
            return "LOW", idx, int(r["minute_of_day"])

    return "NONE", None, None


def path_after_index(g, idx, end_minute=None):
    if idx is None:
        return g.iloc[0:0].copy()
    w = g.loc[idx:].copy()
    if end_minute is not None:
        w = w[w["minute_of_day"] <= end_minute]
    return w


def asia_behavior(day, asia_hi, asia_lo, london_open, london_end):
    out = {
        "asia_first_break": "NONE",
        "asia_first_break_minute": np.nan,
        "asia_both_sides_taken": 0,
        "asia_opposite_after_first": 0,
        "asia_mid_after_first": 0,
        "asia_first_break_rejected_inside": 0,
        "asia_first_break_extension_pips": np.nan,
        "asia_first_break_extension_xrange": np.nan,
    }

    if not np.isfinite(asia_hi) or not np.isfinite(asia_lo) or asia_hi <= asia_lo:
        return out

    side, idx, minute = first_touch_after(
        day, london_open, asia_hi, asia_lo, london_end
    )

    if side in ("NONE", "BOTH"):
        out["asia_first_break"] = side
        out["asia_first_break_minute"] = minute if minute is not None else np.nan
        out["asia_both_sides_taken"] = int(side == "BOTH")
        return out

    out["asia_first_break"] = side
    out["asia_first_break_minute"] = minute

    first_row = day.loc[idx]
    mid = (asia_hi + asia_lo) / 2.0
    rng = asia_hi - asia_lo

    if side == "HIGH":
        out["asia_first_break_rejected_inside"] = int(first_row["close"] < asia_hi)
        path = path_after_index(day, idx, london_end)
        max_ext = (path["high"].max() - asia_hi) / PIP
        out["asia_first_break_extension_pips"] = max_ext
        out["asia_first_break_extension_xrange"] = (
            (path["high"].max() - asia_hi) / rng if rng > 0 else np.nan
        )
        out["asia_opposite_after_first"] = int((path["low"] <= asia_lo).any())
        out["asia_mid_after_first"] = int((path["low"] <= mid).any())
        out["asia_both_sides_taken"] = out["asia_opposite_after_first"]

    elif side == "LOW":
        out["asia_first_break_rejected_inside"] = int(first_row["close"] > asia_lo)
        path = path_after_index(day, idx, london_end)
        max_ext = (asia_lo - path["low"].min()) / PIP
        out["asia_first_break_extension_pips"] = max_ext
        out["asia_first_break_extension_xrange"] = (
            (asia_lo - path["low"].min()) / rng if rng > 0 else np.nan
        )
        out["asia_opposite_after_first"] = int((path["high"] >= asia_hi).any())
        out["asia_mid_after_first"] = int((path["high"] >= mid).any())
        out["asia_both_sides_taken"] = out["asia_opposite_after_first"]

    return out


def previous_day_behavior(day, prev_hi, prev_lo, london_open, day_end):
    out = {
        "pday_first_touch": "NONE",
        "pday_both_touched": 0,
        "pdh_reject": 0,
        "pdl_reject": 0,
        "pdh_extension_pips": np.nan,
        "pdl_extension_pips": np.nan,
    }

    if not np.isfinite(prev_hi) or not np.isfinite(prev_lo):
        return out

    w = day[
        (day["minute_of_day"] >= london_open)
        & (day["minute_of_day"] <= day_end)
    ]

    first = "NONE"
    first_idx = None

    for idx, r in w.iterrows():
        h = r["high"] >= prev_hi
        l = r["low"] <= prev_lo

        if h and l:
            first = "BOTH"
            first_idx = idx
            break
        if h:
            first = "PDH"
            first_idx = idx
            break
        if l:
            first = "PDL"
            first_idx = idx
            break

    out["pday_first_touch"] = first
    out["pday_both_touched"] = int(
        (w["high"] >= prev_hi).any() and (w["low"] <= prev_lo).any()
    )

    if (w["high"] >= prev_hi).any():
        first_pdh = w[w["high"] >= prev_hi].iloc[0]
        out["pdh_reject"] = int(first_pdh["close"] < prev_hi)
        out["pdh_extension_pips"] = (w["high"].max() - prev_hi) / PIP

    if (w["low"] <= prev_lo).any():
        first_pdl = w[w["low"] <= prev_lo].iloc[0]
        out["pdl_reject"] = int(first_pdl["close"] > prev_lo)
        out["pdl_extension_pips"] = (prev_lo - w["low"].min()) / PIP

    return out


def first_impulse_behavior(day, start_minute, end_minute, impulse_pips):
    """
    Start from the open of the first bar at/after session open.
    Find whether +impulse or -impulse is touched first.
    Then ask whether price extends another 50% of impulse or retraces 50%,
    whichever happens first.
    """
    out = {
        "impulse_pips": impulse_pips,
        "first_impulse_side": "NONE",
        "first_impulse_minute": np.nan,
        "extend_before_half_retrace": np.nan,
        "half_retrace_before_extend": np.nan,
    }

    w = day[
        (day["minute_of_day"] >= start_minute)
        & (day["minute_of_day"] <= end_minute)
    ].copy()

    if w.empty:
        return out

    anchor = float(w.iloc[0]["open"])
    up_level = anchor + impulse_pips * PIP
    dn_level = anchor - impulse_pips * PIP

    side = "NONE"
    idx = None

    for i, r in w.iterrows():
        up = r["high"] >= up_level
        dn = r["low"] <= dn_level

        if up and dn:
            return out
        if up:
            side = "UP"
            idx = i
            break
        if dn:
            side = "DOWN"
            idx = i
            break

    if idx is None:
        return out

    out["first_impulse_side"] = side
    out["first_impulse_minute"] = int(day.loc[idx]["minute_of_day"])

    path = day.loc[idx:].copy()
    path = path[path["minute_of_day"] <= end_minute]

    if side == "UP":
        extension = up_level + impulse_pips * EXTEND_MULT * PIP
        retrace = up_level - impulse_pips * RETRACE_MULT * PIP

        for _, r in path.iterrows():
            hit_ext = r["high"] >= extension
            hit_ret = r["low"] <= retrace
            if hit_ext and hit_ret:
                return out
            if hit_ext:
                out["extend_before_half_retrace"] = 1
                out["half_retrace_before_extend"] = 0
                break
            if hit_ret:
                out["extend_before_half_retrace"] = 0
                out["half_retrace_before_extend"] = 1
                break

    else:
        extension = dn_level - impulse_pips * EXTEND_MULT * PIP
        retrace = dn_level + impulse_pips * RETRACE_MULT * PIP

        for _, r in path.iterrows():
            hit_ext = r["low"] <= extension
            hit_ret = r["high"] >= retrace
            if hit_ext and hit_ret:
                return out
            if hit_ext:
                out["extend_before_half_retrace"] = 1
                out["half_retrace_before_extend"] = 0
                break
            if hit_ret:
                out["extend_before_half_retrace"] = 0
                out["half_retrace_before_extend"] = 1
                break

    return out


def build_daily_atlas(df, london_open, ny_open, asia_start, asia_end, day_end):
    daily_bars = df.groupby("date").agg(
        day_open=("open", "first"),
        day_high=("high", "max"),
        day_low=("low", "min"),
        day_close=("close", "last"),
    ).reset_index()

    daily_bars["day_range_pips"] = (daily_bars["day_high"] - daily_bars["day_low"]) / PIP
    daily_bars["day_net_pips"] = (daily_bars["day_close"] - daily_bars["day_open"]) / PIP
    daily_bars["prev_day_high"] = daily_bars["day_high"].shift(1)
    daily_bars["prev_day_low"] = daily_bars["day_low"].shift(1)
    daily_bars["daily_atr20_pips"] = daily_bars["day_range_pips"].rolling(20).mean()

    prev_map = daily_bars.set_index("date")[["prev_day_high","prev_day_low","daily_atr20_pips"]]

    rows = []
    impulse_rows = []

    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)

        full = session_stats(day)

        asia = day[between_wrap(day["minute_of_day"], asia_start, asia_end)]
        asia_s = session_stats(asia)

        pre60 = day[
            (day["minute_of_day"] >= london_open - 60)
            & (day["minute_of_day"] < london_open)
        ]
        pre120 = day[
            (day["minute_of_day"] >= london_open - 120)
            & (day["minute_of_day"] < london_open)
        ]

        london1 = day[
            (day["minute_of_day"] >= london_open)
            & (day["minute_of_day"] < london_open + 60)
        ]
        london4 = day[
            (day["minute_of_day"] >= london_open)
            & (day["minute_of_day"] < london_open + 240)
        ]
        ny1 = day[
            (day["minute_of_day"] >= ny_open)
            & (day["minute_of_day"] < ny_open + 60)
        ]

        p60 = session_stats(pre60)
        p120 = session_stats(pre120)
        l1 = session_stats(london1)
        l4 = session_stats(london4)
        n1 = session_stats(ny1)

        # HOD / LOD times.
        try:
            hod_idx = day["high"].idxmax()
            lod_idx = day["low"].idxmin()
            hod_min = int(day.loc[hod_idx, "minute_of_day"])
            lod_min = int(day.loc[lod_idx, "minute_of_day"])
        except:
            hod_min = np.nan
            lod_min = np.nan

        prev_hi = prev_map.loc[date, "prev_day_high"] if date in prev_map.index else np.nan
        prev_lo = prev_map.loc[date, "prev_day_low"] if date in prev_map.index else np.nan
        datr = prev_map.loc[date, "daily_atr20_pips"] if date in prev_map.index else np.nan

        ab = asia_behavior(
            day, asia_s["high"], asia_s["low"], london_open, london_open + 240
        )
        pb = previous_day_behavior(
            day, prev_hi, prev_lo, london_open, day_end
        )

        row = {
            "date": date,
            "weekday": day.iloc[0]["datetime"].day_name(),

            "day_range_pips": full["range_pips"],
            "day_net_pips": full["net_pips"],
            "daily_atr20_pips": datr,

            "asia_range_pips": asia_s["range_pips"],
            "asia_net_pips": asia_s["net_pips"],

            "pre60_range_pips": p60["range_pips"],
            "pre120_range_pips": p120["range_pips"],

            "london1_range_pips": l1["range_pips"],
            "london1_net_pips": l1["net_pips"],
            "london4_range_pips": l4["range_pips"],
            "london4_net_pips": l4["net_pips"],

            "ny1_range_pips": n1["range_pips"],
            "ny1_net_pips": n1["net_pips"],

            "hod_minute": hod_min,
            "lod_minute": lod_min,

            **ab,
            **pb,
        }
        rows.append(row)

        for imp in IMPULSE_PIPS:
            ib = first_impulse_behavior(
                day, london_open, london_open + 240, imp
            )
            impulse_rows.append({
                "date": date,
                "weekday": day.iloc[0]["datetime"].day_name(),
                "asia_range_pips": asia_s["range_pips"],
                "daily_atr20_pips": datr,
                **ib,
            })

    daily = pd.DataFrame(rows)
    impulses = pd.DataFrame(impulse_rows)

    # Regime labels built only from rolling/whole-sample descriptive bins.
    daily["asia_range_quartile"] = pd.qcut(
        daily["asia_range_pips"],
        q=4,
        labels=["Q1_narrow","Q2","Q3","Q4_wide"],
        duplicates="drop"
    )

    daily["atr_regime"] = pd.qcut(
        daily["daily_atr20_pips"],
        q=3,
        labels=["LOW","MID","HIGH"],
        duplicates="drop"
    )

    return daily, impulses


def add_split(df, disc_dates, val_dates, test_dates):
    out = df.copy()

    def lab(d):
        if d in disc_dates:
            return "DISC"
        if d in val_dates:
            return "VAL"
        if d in test_dates:
            return "TEST"
        return "OTHER"

    out["split"] = out["date"].map(lab)
    return out


def rate_row(df, label, mask, outcome_col):
    g = df[mask & df[outcome_col].notna()]
    if len(g) == 0:
        return None
    return {
        "behavior": label,
        "samples": len(g),
        "rate": float(g[outcome_col].mean()),
        "events": int(g[outcome_col].sum()),
    }


def stable_candidate(rows_by_split, label, min_disc=MIN_DISC, min_val=MIN_VAL, min_test=MIN_TEST):
    try:
        d = rows_by_split["DISC"]
        v = rows_by_split["VAL"]
        t = rows_by_split["TEST"]
    except KeyError:
        return None

    if d["samples"] < min_disc or v["samples"] < min_val or t["samples"] < min_test:
        return None

    # Stability score: smaller is better.
    spread = max(d["rate"], v["rate"], t["rate"]) - min(d["rate"], v["rate"], t["rate"])
    avg = np.mean([d["rate"], v["rate"], t["rate"]])

    return {
        "behavior": label,
        "DISC_n": d["samples"],
        "DISC_rate": d["rate"],
        "VAL_n": v["samples"],
        "VAL_rate": v["rate"],
        "TEST_n": t["samples"],
        "TEST_rate": t["rate"],
        "avg_rate": avg,
        "split_spread": spread,
        "stable": spread <= 0.10,
    }


def build_behavior_tables(daily, impulses):
    asia_rows = []
    pday_rows = []
    regime_rows = []
    candidate_rows = []

    # Asia behaviors.
    asia_specs = [
        ("Asia first break reaches midpoint afterward",
         daily["asia_first_break"].isin(["HIGH","LOW"]),
         "asia_mid_after_first"),
        ("Asia first break eventually reaches opposite side",
         daily["asia_first_break"].isin(["HIGH","LOW"]),
         "asia_opposite_after_first"),
        ("Asia first break candle rejects back inside",
         daily["asia_first_break"].isin(["HIGH","LOW"]),
         "asia_first_break_rejected_inside"),
    ]

    # Add conditional Asia-range quartile behaviors.
    for q in daily["asia_range_quartile"].dropna().unique():
        asia_specs.append((
            f"{q}: first Asia break reaches opposite side",
            daily["asia_first_break"].isin(["HIGH","LOW"]) & (daily["asia_range_quartile"] == q),
            "asia_opposite_after_first"
        ))
        asia_specs.append((
            f"{q}: first Asia break reaches midpoint",
            daily["asia_first_break"].isin(["HIGH","LOW"]) & (daily["asia_range_quartile"] == q),
            "asia_mid_after_first"
        ))

    for label, mask, col in asia_specs:
        split_map = {}
        for split in ["DISC","VAL","TEST"]:
            submask = mask & (daily["split"] == split)
            r = rate_row(daily, label, submask, col)
            if r:
                split_map[split] = r
                asia_rows.append({"split": split, **r})
        cand = stable_candidate(split_map, label)
        if cand:
            candidate_rows.append(cand)

    # Previous-day behaviors.
    p_specs = [
        ("PDH touch rejects below PDH",
         daily["pdh_extension_pips"].notna(), "pdh_reject"),
        ("PDL touch rejects above PDL",
         daily["pdl_extension_pips"].notna(), "pdl_reject"),
        ("Both previous-day extremes touched same day",
         daily["pday_first_touch"].isin(["PDH","PDL","BOTH"]), "pday_both_touched"),
    ]

    for label, mask, col in p_specs:
        split_map = {}
        for split in ["DISC","VAL","TEST"]:
            r = rate_row(daily, label, mask & (daily["split"] == split), col)
            if r:
                split_map[split] = r
                pday_rows.append({"split": split, **r})
        cand = stable_candidate(split_map, label)
        if cand:
            candidate_rows.append(cand)

    # Impulse behaviors.
    impulse_rows = []
    for imp in IMPULSE_PIPS:
        for split in ["DISC","VAL","TEST"]:
            g = impulses[
                (impulses["impulse_pips"] == imp)
                & (impulses["split"] == split)
                & impulses["extend_before_half_retrace"].notna()
            ]
            if len(g):
                impulse_rows.append({
                    "impulse_pips": imp,
                    "split": split,
                    "samples": len(g),
                    "extend_before_half_retrace_rate": g["extend_before_half_retrace"].mean(),
                })

        split_map = {}
        for split in ["DISC","VAL","TEST"]:
            g = impulses[
                (impulses["impulse_pips"] == imp)
                & (impulses["split"] == split)
                & impulses["extend_before_half_retrace"].notna()
            ]
            if len(g):
                split_map[split] = {
                    "samples": len(g),
                    "rate": float(g["extend_before_half_retrace"].mean())
                }
        cand = stable_candidate(
            split_map,
            f"After first {imp}p impulse, extend another {int(imp*EXTEND_MULT)}p before retracing {int(imp*RETRACE_MULT)}p"
        )
        if cand:
            candidate_rows.append(cand)

    # Regime behaviors: London 1h range >= Asia range * 0.5, 1.0, 1.5
    for multiple in [0.5, 1.0, 1.5]:
        outcome = (
            daily["london1_range_pips"] >= daily["asia_range_pips"] * multiple
        ).astype(float)
        col = f"_tmp_london1_{multiple}"
        daily[col] = outcome

        for q in daily["asia_range_quartile"].dropna().unique():
            label = f"{q}: London first-hour range >= {multiple:.1f}x Asia range"
            mask = daily["asia_range_quartile"] == q
            split_map = {}
            for split in ["DISC","VAL","TEST"]:
                r = rate_row(daily, label, mask & (daily["split"] == split), col)
                if r:
                    split_map[split] = r
                    regime_rows.append({"split": split, **r})
            cand = stable_candidate(split_map, label)
            if cand:
                candidate_rows.append(cand)

    return (
        pd.DataFrame(asia_rows),
        pd.DataFrame(pday_rows),
        pd.DataFrame(impulse_rows),
        pd.DataFrame(regime_rows),
        pd.DataFrame(candidate_rows)
    )


def session_summary(daily):
    rows = []

    metrics = [
        "asia_range_pips",
        "pre60_range_pips",
        "pre120_range_pips",
        "london1_range_pips",
        "london4_range_pips",
        "ny1_range_pips",
        "day_range_pips",
    ]

    for split in ["DISC","VAL","TEST"]:
        g = daily[daily["split"] == split]
        for m in metrics:
            x = g[m].dropna()
            if len(x):
                rows.append({
                    "split": split,
                    "metric": m,
                    "samples": len(x),
                    "mean": x.mean(),
                    "median": x.median(),
                    "p25": x.quantile(0.25),
                    "p75": x.quantile(0.75),
                })

    return pd.DataFrame(rows)


def high_low_timing(daily):
    rows = []

    for split in ["DISC","VAL","TEST"]:
        g = daily[daily["split"] == split]

        for name, col in [("HOD","hod_minute"),("LOD","lod_minute")]:
            x = g[col].dropna().astype(int)
            if not len(x):
                continue

            hours = (x // 60).value_counts().sort_index()

            for hour, count in hours.items():
                rows.append({
                    "split": split,
                    "extreme": name,
                    "hour": int(hour),
                    "count": int(count),
                    "share": count / len(x),
                })

    return pd.DataFrame(rows)


def write_report(outdir, daily, impulses, candidates, session_df, london_open, ny_open, asia_start, asia_end):
    report = []
    report.append("CANDLE DNA v25 — EURUSD MULTI-YEAR BEHAVIOR ATLAS")
    report.append("="*110)
    report.append("")
    report.append(f"Daily observations: {len(daily)}")
    report.append(
        f"Broker-server windows: Asia {asia_start//60:02d}:{asia_start%60:02d}"
        f"–{asia_end//60:02d}:{asia_end%60:02d} | "
        f"London open {london_open//60:02d}:{london_open%60:02d} | "
        f"NY open {ny_open//60:02d}:{ny_open%60:02d}"
    )
    report.append("")

    report.append("CORE SESSION MEDIANS")
    report.append("-"*110)

    med = session_df[session_df["split"] == "TEST"]
    for _, r in med.iterrows():
        report.append(
            f"{r['metric']:<24} | TEST median {r['median']:6.2f}p | "
            f"IQR {r['p25']:6.2f}–{r['p75']:6.2f}p | n={int(r['samples'])}"
        )

    report.append("")
    report.append("MOST STABLE CANDIDATE BEHAVIORS")
    report.append("-"*110)

    if candidates.empty:
        report.append("No candidate behavior met minimum sample/stability requirements.")
    else:
        ranked = candidates.copy()
        # High rates and low split spread are most interesting.
        ranked["score"] = ranked["avg_rate"] - ranked["split_spread"]
        ranked = ranked.sort_values(
            ["stable","score","TEST_n"],
            ascending=[False,False,False]
        )

        for _, r in ranked.head(40).iterrows():
            report.append(
                f"{'STABLE' if r['stable'] else 'UNSTABLE':<8} | "
                f"DISC {r['DISC_rate']*100:5.1f}% n={int(r['DISC_n']):>4} | "
                f"VAL {r['VAL_rate']*100:5.1f}% n={int(r['VAL_n']):>3} | "
                f"TEST {r['TEST_rate']*100:5.1f}% n={int(r['TEST_n']):>3} | "
                f"{r['behavior']}"
            )

    report.append("")
    report.append("HOW TO USE THIS")
    report.append("-"*110)
    report.append(
        "Look for behaviors with large samples, similar rates across all three chronological splits, "
        "and probabilities materially away from 50%."
    )
    report.append(
        "Those behaviors are the candidates to convert into an actual trading hypothesis in v26."
    )
    report.append(
        "Do not optimize entries or stops around a behavior until it survives this descriptive stability test."
    )

    (outdir / "v25_report.txt").write_text("\n".join(report), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", help="Clean M5 CSV from v24.1")
    ap.add_argument("--out", default="behavior_atlas_v25_output")

    ap.add_argument("--london-open", default="10:00", help="BROKER SERVER TIME")
    ap.add_argument("--ny-open", default="15:30", help="BROKER SERVER TIME")

    # Default Asia range = 8 hours immediately before London open.
    ap.add_argument("--asia-start", default="02:00", help="BROKER SERVER TIME")
    ap.add_argument("--asia-end", default="10:00", help="BROKER SERVER TIME")

    ap.add_argument("--day-end", default="23:55", help="BROKER SERVER TIME")

    args = ap.parse_args()

    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    lh, lm = parse_hhmm(args.london_open)
    nh, nm = parse_hhmm(args.ny_open)
    ah, am = parse_hhmm(args.asia_start)
    aeh, aem = parse_hhmm(args.asia_end)
    dh, dm = parse_hhmm(args.day_end)

    london_open = minute_of_day(lh, lm)
    ny_open = minute_of_day(nh, nm)
    asia_start = minute_of_day(ah, am)
    asia_end = minute_of_day(aeh, aem)
    day_end = minute_of_day(dh, dm)

    print("="*110)
    print("CANDLE DNA v25 — EURUSD MULTI-YEAR BEHAVIOR ATLAS")
    print("="*110)
    print("Loading:", args.csv)

    df = load_data(args.csv)

    print(f"M5 candles: {len(df):,}")
    print(f"First: {df['datetime'].min()}")
    print(f"Last:  {df['datetime'].max()}")

    daily, impulses = build_daily_atlas(
        df,
        london_open,
        ny_open,
        asia_start,
        asia_end,
        day_end
    )

    dates = sorted(daily["date"].unique())
    disc, val, test = split_dates(dates)

    daily = add_split(daily, disc, val, test)
    impulses = add_split(impulses, disc, val, test)

    print(
        f"Daily observations: {len(daily)} | "
        f"DISC {len(disc)} | VAL {len(val)} | TEST {len(test)}"
    )

    asia_df, pday_df, impulse_df, regime_df, candidate_df = build_behavior_tables(
        daily, impulses
    )

    session_df = session_summary(daily)
    timing_df = high_low_timing(daily)

    daily.to_csv(outdir / "v25_daily_atlas.csv", index=False)
    session_df.to_csv(outdir / "v25_session_summary.csv", index=False)
    asia_df.to_csv(outdir / "v25_asia_sweep_behaviors.csv", index=False)
    pday_df.to_csv(outdir / "v25_previous_day_behaviors.csv", index=False)
    impulse_df.to_csv(outdir / "v25_impulse_behaviors.csv", index=False)
    timing_df.to_csv(outdir / "v25_high_low_timing.csv", index=False)
    regime_df.to_csv(outdir / "v25_regime_behaviors.csv", index=False)
    candidate_df.to_csv(outdir / "v25_candidate_behaviors.csv", index=False)

    write_report(
        outdir,
        daily,
        impulses,
        candidate_df,
        session_df,
        london_open,
        ny_open,
        asia_start,
        asia_end
    )

    print("\n" + "="*110)
    print("V25 BEHAVIOR ATLAS COMPLETE")
    print("="*110)
    print("Output folder:", outdir.resolve())
    print("\nPaste v25_report.txt here.")
    print("If something interesting appears, we can inspect the supporting CSV without uploading the full M5 dataset.")


if __name__ == "__main__":
    main()
