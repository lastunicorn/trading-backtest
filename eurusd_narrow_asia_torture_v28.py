#!/usr/bin/env python3
"""
Candle DNA v28 — Narrow Asia Fade Robustness / Torture Test
===========================================================

Purpose
-------
Do NOT search for a new strategy.

Freeze the strategy family discovered in v27 and try to break it.

Core strategy under test
------------------------
Environment:
    Asia range <= frozen discovery Q1 threshold

Signal:
    First break of Asia after London open

Filter:
    Breakout-bar relative volume >= 1.6

Entry:
    BOUNDARY RE-ENTRY
    After the first break, wait for price to cross back through the broken
    Asia boundary. Enter at that boundary.

Target:
    Asia midpoint

Stops:
    Torture-test the v27 profitable neighborhood, not a giant new search:
        Fixed: 6, 7, 10, 12, 15 pips
        Dynamic: 0.50x, 0.60x, 0.75x, 1.00x Asia range

Costs:
    1.7 pips per completed trade

Main robustness tests
---------------------
1) Long vs short separately
2) Monday-Friday
3) Month-of-year
4) Calendar year
5) Asia-range buckets
6) Relative-volume buckets
7) Breakout-time buckets
8) Stop-neighborhood comparison
9) Walk-forward / expanding-window testing

Walk-forward philosophy
-----------------------
NO re-optimization of the signal in each period.

The strategy is frozen:
    Narrow Asia
    RelVol >= 1.6
    Boundary re-entry
    Midpoint target

Only the already-discovered stop neighborhood is compared descriptively.

Walk-forward windows:
    2020-2021 -> test 2022
    2020-2022 -> test 2023
    2020-2023 -> test 2024
    2020-2024 -> test 2025
    2020-2025 -> test 2026

Research standard
-----------------
The strategy becomes substantially more credible if:
- most years are positive
- both long and short directions work
- no single weekday/month explains the edge
- relative-volume performance generally improves with volume
- multiple nearby stops remain positive
- walk-forward test years are broadly positive
- performance does not depend on one isolated regime

Inputs
------
Use the clean local M5 dataset:

    research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv

Run
---
python eurusd_narrow_asia_torture_v28.py ^
  "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv"

Outputs
-------
narrow_asia_v28_output/
    v28_report.txt
    v28_trade_log_all_stops.csv
    v28_stop_comparison.csv
    v28_direction_breakdown.csv
    v28_weekday_breakdown.csv
    v28_month_breakdown.csv
    v28_year_breakdown.csv
    v28_asia_range_breakdown.csv
    v28_relvol_breakdown.csv
    v28_time_breakdown.csv
    v28_walk_forward.csv
    v28_robustness_scorecard.csv
"""

import argparse
from pathlib import Path
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001
COST_PIPS = 1.7

FIXED_STOPS = [6, 7, 10, 12, 15]
RANGE_STOPS = [0.50, 0.60, 0.75, 1.00]

REL_VOL_MIN = 1.6

# Default broker-server windows from prior research
DEFAULT_ASIA_START = "02:00"
DEFAULT_ASIA_END = "10:00"
DEFAULT_LONDON_OPEN = "10:00"
DEFAULT_STUDY_END = "14:00"

# For summary tables
ASIA_BUCKETS = [0, 10, 12.5, 15, 17.5, 20, 21.72, np.inf]
ASIA_LABELS = ["<10", "10-12.5", "12.5-15", "15-17.5", "17.5-20", "20-21.72", ">21.72"]

RELVOL_BUCKETS = [0, 1.0, 1.25, 1.50, 1.75, 2.0, 2.5, 3.0, np.inf]
RELVOL_LABELS = ["<1.0", "1.0-1.25", "1.25-1.5", "1.5-1.75", "1.75-2.0", "2.0-2.5", "2.5-3.0", "3.0+"]

TIME_BUCKETS = [-1, 0, 5, 10, 15, 20, 30, 45, 60, 90, 120, 240, np.inf]
TIME_LABELS = ["0m", "1-5", "6-10", "11-15", "16-20", "21-30", "31-45", "46-60", "61-90", "91-120", "121-240", "240m+"]

MIN_GROUP_TRADES = 5


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
    df["year"] = df["datetime"].dt.year
    df["month"] = df["datetime"].dt.month
    df["weekday_num"] = df["datetime"].dt.dayofweek
    df["weekday"] = df["datetime"].dt.day_name()
    df["minute_of_day"] = df["datetime"].dt.hour * 60 + df["datetime"].dt.minute

    df = df[df["weekday_num"] < 5].copy().reset_index(drop=True)

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


def first_break(day, asia_hi, asia_lo, london_open, study_end):
    w = day[
        (day["minute_of_day"] >= london_open)
        & (day["minute_of_day"] <= study_end)
    ]

    for idx, r in w.iterrows():
        up = r["high"] >= asia_hi
        dn = r["low"] <= asia_lo

        if up and dn:
            return {"ambiguous": 1}

        if up:
            return {
                "ambiguous": 0,
                "idx": idx,
                "side": "HIGH",
                "break_minute": int(r["minute_of_day"]),
                "break_relvol20": float(r["relvol20"]) if np.isfinite(r["relvol20"]) else np.nan,
                "penetration_pips": (float(r["high"]) - asia_hi) / PIP,
            }

        if dn:
            return {
                "ambiguous": 0,
                "idx": idx,
                "side": "LOW",
                "break_minute": int(r["minute_of_day"]),
                "break_relvol20": float(r["relvol20"]) if np.isfinite(r["relvol20"]) else np.nan,
                "penetration_pips": (asia_lo - float(r["low"])) / PIP,
            }

    return None


def boundary_reentry(day, info, asia_hi, asia_lo, study_end):
    idx = info["idx"]
    side = info["side"]

    path = day.loc[idx:].copy()
    path = path[path["minute_of_day"] <= study_end]

    # Avoid same-bar path assumptions
    path = path.iloc[1:]

    if side == "HIGH":
        for j, r in path.iterrows():
            if r["low"] <= asia_hi:
                return {
                    "entry": asia_hi,
                    "entry_idx": j,
                    "entry_minute": int(r["minute_of_day"]),
                }

    else:
        for j, r in path.iterrows():
            if r["high"] >= asia_lo:
                return {
                    "entry": asia_lo,
                    "entry_idx": j,
                    "entry_minute": int(r["minute_of_day"]),
                }

    return None


def stop_price(side, entry, asia_range_pips, stop_mode, stop_value):
    if stop_mode == "FIXED":
        dist = float(stop_value)
    else:
        dist = asia_range_pips * float(stop_value)

    if side == "HIGH":   # short
        stop = entry + dist * PIP
    else:                # long
        stop = entry - dist * PIP

    return stop, dist


def simulate_trade(day, info, entry_info, asia_mid, asia_range_pips, stop_mode, stop_value, study_end):
    side = info["side"]
    entry = float(entry_info["entry"])
    entry_idx = int(entry_info["entry_idx"])

    stop, stop_pips = stop_price(
        side, entry, asia_range_pips, stop_mode, stop_value
    )

    target = float(asia_mid)

    if side == "HIGH":
        reward_pips = (entry - target) / PIP
    else:
        reward_pips = (target - entry) / PIP

    if reward_pips <= 0 or stop_pips <= 0:
        return None

    path = day.loc[entry_idx:].copy()
    path = path[path["minute_of_day"] <= study_end]

    # Start resolving from next bar to avoid same-bar ambiguity.
    path_eval = path.iloc[1:].copy() if len(path) > 1 else path.iloc[0:0].copy()

    exit_reason = "TIME"
    exit_price = float(path.iloc[-1]["close"]) if len(path) else entry
    exit_minute = int(path.iloc[-1]["minute_of_day"]) if len(path) else entry_info["entry_minute"]

    for _, r in path_eval.iterrows():
        h = float(r["high"])
        l = float(r["low"])

        if side == "HIGH":
            hit_sl = h >= stop
            hit_tp = l <= target
        else:
            hit_sl = l <= stop
            hit_tp = h >= target

        if hit_sl and hit_tp:
            exit_reason = "SL"
            exit_price = stop
            exit_minute = int(r["minute_of_day"])
            break

        if hit_sl:
            exit_reason = "SL"
            exit_price = stop
            exit_minute = int(r["minute_of_day"])
            break

        if hit_tp:
            exit_reason = "TP"
            exit_price = target
            exit_minute = int(r["minute_of_day"])
            break

    if side == "HIGH":
        gross_pips = (entry - exit_price) / PIP
        trade_dir = "SHORT"
    else:
        gross_pips = (exit_price - entry) / PIP
        trade_dir = "LONG"

    net_pips = gross_pips - COST_PIPS

    return {
        "trade_direction": trade_dir,
        "entry": entry,
        "stop": stop,
        "target": target,
        "stop_pips": stop_pips,
        "reward_to_mid_pips": reward_pips,
        "entry_minute": entry_info["entry_minute"],
        "exit_minute": exit_minute,
        "exit_reason": exit_reason,
        "gross_pips": gross_pips,
        "net_pips": net_pips,
        "net_r": net_pips / stop_pips,
        "win": int(net_pips > 0),
    }


def max_drawdown(values):
    a = np.asarray(values, dtype=float)
    if len(a) == 0:
        return np.nan
    eq = np.concatenate([[0.0], np.cumsum(a)])
    peak = np.maximum.accumulate(eq)
    return float(np.max(peak - eq))


def max_consecutive_losses(values):
    max_run = 0
    cur = 0

    for x in values:
        if x < 0:
            cur += 1
            max_run = max(max_run, cur)
        else:
            cur = 0

    return max_run


def summarize(g):
    if len(g) == 0:
        return {}

    pnl = g["net_pips"].to_numpy(float)
    wins = g[g["net_pips"] > 0]
    losses = g[g["net_pips"] <= 0]

    gp = wins["net_pips"].sum() if len(wins) else 0.0
    gl = -losses["net_pips"].sum() if len(losses) else 0.0

    return {
        "trades": len(g),
        "win_rate": float((g["net_pips"] > 0).mean()),
        "avg_net_pips": float(g["net_pips"].mean()),
        "median_net_pips": float(g["net_pips"].median()),
        "total_net_pips": float(g["net_pips"].sum()),
        "profit_factor": float(gp / gl) if gl > 0 else np.inf,
        "avg_net_r": float(g["net_r"].mean()),
        "avg_win_pips": float(wins["net_pips"].mean()) if len(wins) else np.nan,
        "avg_loss_pips": float(losses["net_pips"].mean()) if len(losses) else np.nan,
        "max_drawdown_pips": max_drawdown(pnl),
        "max_consecutive_losses": max_consecutive_losses(pnl),
        "tp_rate": float((g["exit_reason"] == "TP").mean()),
        "sl_rate": float((g["exit_reason"] == "SL").mean()),
    }


def build_trade_log_for_stop(
    df,
    narrow_threshold,
    asia_start,
    asia_end,
    london_open,
    study_end,
    stop_mode,
    stop_value
):
    rows = []

    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)

        a = asia_stats(day, asia_start, asia_end)
        if a is None or a["range_pips"] > narrow_threshold:
            continue

        info = first_break(
            day,
            a["high"],
            a["low"],
            london_open,
            study_end
        )

        if info is None or info.get("ambiguous", 0):
            continue

        # Frozen v27 filter
        if not np.isfinite(info["break_relvol20"]) or info["break_relvol20"] < REL_VOL_MIN:
            continue

        entry_info = boundary_reentry(
            day,
            info,
            a["high"],
            a["low"],
            study_end
        )

        if entry_info is None:
            continue

        tr = simulate_trade(
            day,
            info,
            entry_info,
            a["mid"],
            a["range_pips"],
            stop_mode,
            stop_value,
            study_end
        )

        if tr is None:
            continue

        first_dt = day.iloc[0]["datetime"]

        rows.append({
            "date": date,
            "year": int(first_dt.year),
            "month": int(first_dt.month),
            "month_name": first_dt.month_name(),
            "weekday": first_dt.day_name(),
            "asia_range_pips": a["range_pips"],
            "break_side": info["side"],
            "break_minutes_after_london": info["break_minute"] - london_open,
            "break_relvol20": info["break_relvol20"],
            "break_penetration_pips": info["penetration_pips"],
            "stop_mode": stop_mode,
            "stop_value": stop_value,
            **tr,
        })

    return pd.DataFrame(rows)


def breakdown(log, group_col):
    rows = []

    for key, g in log.groupby(group_col, observed=True):
        if len(g) < MIN_GROUP_TRADES:
            # Keep small groups too, but clearly flag low sample.
            sample_flag = "LOW_SAMPLE"
        else:
            sample_flag = "OK"

        s = summarize(g)

        rows.append({
            group_col: key,
            "sample_flag": sample_flag,
            **s
        })

    return pd.DataFrame(rows)


def add_buckets(log):
    x = log.copy()

    x["asia_range_bucket"] = pd.cut(
        x["asia_range_pips"],
        bins=ASIA_BUCKETS,
        labels=ASIA_LABELS,
        right=False
    )

    x["relvol_bucket"] = pd.cut(
        x["break_relvol20"],
        bins=RELVOL_BUCKETS,
        labels=RELVOL_LABELS,
        right=False
    )

    x["time_bucket"] = pd.cut(
        x["break_minutes_after_london"],
        bins=TIME_BUCKETS,
        labels=TIME_LABELS,
        right=True
    )

    return x


def compare_stops(all_logs):
    rows = []

    for (mode, value), g in all_logs.groupby(["stop_mode", "stop_value"]):
        s = summarize(g)

        positive_years = 0
        negative_years = 0
        years = 0

        for _, yg in g.groupby("year"):
            years += 1
            if yg["net_pips"].sum() > 0:
                positive_years += 1
            elif yg["net_pips"].sum() < 0:
                negative_years += 1

        rows.append({
            "stop_mode": mode,
            "stop_value": value,
            **s,
            "years": years,
            "positive_years": positive_years,
            "negative_years": negative_years,
            "positive_year_fraction": positive_years/years if years else np.nan,
        })

    out = pd.DataFrame(rows)

    if len(out):
        out = out.sort_values(
            ["positive_year_fraction", "profit_factor", "avg_net_pips"],
            ascending=[False, False, False]
        )

    return out


def expanding_walk_forward(log):
    """
    No re-optimization.
    For each stop configuration, report expanding historical train and next-year test.
    """
    rows = []

    available_years = sorted(log["year"].unique())

    for (mode, value), sg in log.groupby(["stop_mode", "stop_value"]):
        for test_year in [2022, 2023, 2024, 2025, 2026]:
            if test_year not in available_years:
                continue

            train = sg[sg["year"] < test_year]
            test = sg[sg["year"] == test_year]

            if len(train) == 0 or len(test) == 0:
                continue

            tr = summarize(train)
            te = summarize(test)

            rows.append({
                "stop_mode": mode,
                "stop_value": value,
                "train_end_year": test_year - 1,
                "test_year": test_year,

                "train_trades": tr["trades"],
                "train_avg_net_pips": tr["avg_net_pips"],
                "train_profit_factor": tr["profit_factor"],

                "test_trades": te["trades"],
                "test_win_rate": te["win_rate"],
                "test_avg_net_pips": te["avg_net_pips"],
                "test_total_net_pips": te["total_net_pips"],
                "test_profit_factor": te["profit_factor"],
                "test_max_dd_pips": te["max_drawdown_pips"],
                "test_positive": te["avg_net_pips"] > 0,
            })

    return pd.DataFrame(rows)


def robustness_scorecard(stop_df, walk_df):
    rows = []

    for _, s in stop_df.iterrows():
        mode = s["stop_mode"]
        value = s["stop_value"]

        wf = walk_df[
            (walk_df["stop_mode"] == mode)
            & (walk_df["stop_value"] == value)
        ]

        wf_tests = len(wf)
        wf_positive = int(wf["test_positive"].sum()) if wf_tests else 0

        rows.append({
            "stop_mode": mode,
            "stop_value": value,
            "trades": s["trades"],
            "avg_net_pips": s["avg_net_pips"],
            "profit_factor": s["profit_factor"],
            "positive_years": s["positive_years"],
            "negative_years": s["negative_years"],
            "positive_year_fraction": s["positive_year_fraction"],
            "walk_forward_tests": wf_tests,
            "walk_forward_positive": wf_positive,
            "walk_forward_positive_fraction": wf_positive/wf_tests if wf_tests else np.nan,
            "ROBUSTNESS_PASS": (
                s["profit_factor"] > 1.0
                and s["avg_net_pips"] > 0
                and s["positive_year_fraction"] >= 0.70
                and wf_tests >= 3
                and wf_positive/wf_tests >= 0.60
            ) if wf_tests else False
        })

    out = pd.DataFrame(rows)

    if len(out):
        out = out.sort_values(
            ["ROBUSTNESS_PASS", "walk_forward_positive_fraction", "positive_year_fraction", "profit_factor"],
            ascending=[False, False, False, False]
        )

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out", default="narrow_asia_v28_output")
    ap.add_argument("--asia-start", default=DEFAULT_ASIA_START)
    ap.add_argument("--asia-end", default=DEFAULT_ASIA_END)
    ap.add_argument("--london-open", default=DEFAULT_LONDON_OPEN)
    ap.add_argument("--study-end", default=DEFAULT_STUDY_END)
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

    print("="*124)
    print("CANDLE DNA v28 — NARROW ASIA FADE ROBUSTNESS / TORTURE TEST")
    print("="*124)
    print("Loading:", args.csv)

    df = load_data(args.csv)

    print(f"M5 candles: {len(df):,}")
    print(f"First: {df['datetime'].min()}")
    print(f"Last:  {df['datetime'].max()}")

    # Freeze narrow threshold from original chronological discovery segment.
    day_ranges = build_day_ranges(df, asia_start, asia_end)
    dates = sorted(day_ranges["date"].unique())
    disc_dates, val_dates, test_dates = split_dates(dates)

    disc_ranges = day_ranges[
        day_ranges["date"].isin(disc_dates)
    ]["asia_range_pips"].dropna()

    narrow_threshold = float(disc_ranges.quantile(0.25))

    print(f"Frozen discovery-Q1 narrow-Asia threshold: <= {narrow_threshold:.2f} pips")
    print(f"Frozen filter: RelVol >= {REL_VOL_MIN:.1f}")
    print("Frozen entry: boundary re-entry")
    print("Frozen target: Asia midpoint")

    stop_configs = [("FIXED", float(x)) for x in FIXED_STOPS] + \
                   [("RANGE_MULT", float(x)) for x in RANGE_STOPS]

    logs = []

    for i, (mode, value) in enumerate(stop_configs, 1):
        print(f"[{i}/{len(stop_configs)}] Building trades for {mode} {value}")

        g = build_trade_log_for_stop(
            df,
            narrow_threshold,
            asia_start,
            asia_end,
            london_open,
            study_end,
            mode,
            value
        )

        if len(g):
            logs.append(g)

    if not logs:
        raise RuntimeError("No trades generated.")

    all_logs = pd.concat(logs, ignore_index=True)
    all_logs = add_buckets(all_logs)

    all_logs.to_csv(outdir/"v28_trade_log_all_stops.csv", index=False)

    # Stop comparison
    stop_df = compare_stops(all_logs)
    stop_df.to_csv(outdir/"v28_stop_comparison.csv", index=False)

    # Use v27 primary stop for behavioral breakdown:
    # RANGE_MULT 1.00
    primary = all_logs[
        (all_logs["stop_mode"] == "RANGE_MULT")
        & (np.isclose(all_logs["stop_value"], 1.00))
    ].copy()

    if len(primary) == 0:
        raise RuntimeError("Primary RANGE_MULT 1.00 trade log missing.")

    direction_df = breakdown(primary, "trade_direction")
    weekday_df = breakdown(primary, "weekday")
    month_df = breakdown(primary, "month_name")
    year_df = breakdown(primary, "year")
    asia_df = breakdown(primary, "asia_range_bucket")
    relvol_df = breakdown(primary, "relvol_bucket")
    time_df = breakdown(primary, "time_bucket")

    direction_df.to_csv(outdir/"v28_direction_breakdown.csv", index=False)
    weekday_df.to_csv(outdir/"v28_weekday_breakdown.csv", index=False)
    month_df.to_csv(outdir/"v28_month_breakdown.csv", index=False)
    year_df.to_csv(outdir/"v28_year_breakdown.csv", index=False)
    asia_df.to_csv(outdir/"v28_asia_range_breakdown.csv", index=False)
    relvol_df.to_csv(outdir/"v28_relvol_breakdown.csv", index=False)
    time_df.to_csv(outdir/"v28_time_breakdown.csv", index=False)

    # Walk-forward for all stop neighbors.
    walk_df = expanding_walk_forward(all_logs)
    walk_df.to_csv(outdir/"v28_walk_forward.csv", index=False)

    score_df = robustness_scorecard(stop_df, walk_df)
    score_df.to_csv(outdir/"v28_robustness_scorecard.csv", index=False)

    report = []

    report.append("CANDLE DNA v28 — NARROW ASIA FADE ROBUSTNESS / TORTURE TEST")
    report.append("="*124)
    report.append("")
    report.append(f"Frozen narrow-Asia threshold: <= {narrow_threshold:.2f} pips")
    report.append(f"Frozen relative-volume filter: >= {REL_VOL_MIN:.1f}")
    report.append("Frozen entry: boundary re-entry")
    report.append("Frozen target: Asia midpoint")
    report.append(f"Cost model: {COST_PIPS:.1f} pips / completed trade")
    report.append("")

    report.append("STOP NEIGHBORHOOD")
    report.append("-"*124)

    for _, r in stop_df.iterrows():
        report.append(
            f"{r['stop_mode']:<10} {r['stop_value']:>5.2f} | "
            f"trades {int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | "
            f"PF {r['profit_factor']:.2f} | "
            f"total {r['total_net_pips']:+.1f}p | "
            f"DD {r['max_drawdown_pips']:.1f}p | "
            f"positive years {int(r['positive_years'])}/{int(r['years'])}"
        )

    report.append("")
    report.append("PRIMARY STOP: RANGE_MULT 1.00")
    report.append("-"*124)

    ps = summarize(primary)

    report.append(
        f"Trades {ps['trades']} | WR {ps['win_rate']*100:.1f}% | "
        f"avg {ps['avg_net_pips']:+.2f}p | PF {ps['profit_factor']:.2f} | "
        f"total {ps['total_net_pips']:+.1f}p | DD {ps['max_drawdown_pips']:.1f}p | "
        f"max losses {ps['max_consecutive_losses']}"
    )

    report.append("")
    report.append("LONG vs SHORT")
    report.append("-"*124)

    for _, r in direction_df.iterrows():
        report.append(
            f"{r['trade_direction']:<5} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | "
            f"PF {r['profit_factor']:.2f} | "
            f"total {r['total_net_pips']:+.1f}p"
        )

    report.append("")
    report.append("YEAR-BY-YEAR")
    report.append("-"*124)

    for _, r in year_df.sort_values("year").iterrows():
        report.append(
            f"{int(r['year'])} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | "
            f"PF {r['profit_factor']:.2f} | "
            f"total {r['total_net_pips']:+.1f}p | "
            f"DD {r['max_drawdown_pips']:.1f}p"
        )

    report.append("")
    report.append("WEEKDAY")
    report.append("-"*124)

    weekday_order = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
    wd = weekday_df.copy()
    wd["weekday"] = pd.Categorical(wd["weekday"], categories=weekday_order, ordered=True)
    wd = wd.sort_values("weekday")

    for _, r in wd.iterrows():
        report.append(
            f"{str(r['weekday']):<9} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | PF {r['profit_factor']:.2f}"
        )

    report.append("")
    report.append("MONTH OF YEAR")
    report.append("-"*124)

    month_order = [
        "January","February","March","April","May","June",
        "July","August","September","October","November","December"
    ]
    md = month_df.copy()
    md["month_name"] = pd.Categorical(md["month_name"], categories=month_order, ordered=True)
    md = md.sort_values("month_name")

    for _, r in md.iterrows():
        report.append(
            f"{str(r['month_name']):<10} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | PF {r['profit_factor']:.2f} | "
            f"{r['sample_flag']}"
        )

    report.append("")
    report.append("ASIA RANGE BUCKETS")
    report.append("-"*124)

    for _, r in asia_df.iterrows():
        report.append(
            f"{str(r['asia_range_bucket']):<10} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | PF {r['profit_factor']:.2f}"
        )

    report.append("")
    report.append("RELATIVE VOLUME BUCKETS")
    report.append("-"*124)

    for _, r in relvol_df.iterrows():
        report.append(
            f"{str(r['relvol_bucket']):<10} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | PF {r['profit_factor']:.2f}"
        )

    report.append("")
    report.append("BREAKOUT TIME BUCKETS")
    report.append("-"*124)

    for _, r in time_df.iterrows():
        report.append(
            f"{str(r['time_bucket']):<10} | n={int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | PF {r['profit_factor']:.2f}"
        )

    report.append("")
    report.append("EXPANDING WALK-FORWARD")
    report.append("-"*124)
    report.append("Frozen signal. No annual signal re-optimization.")
    report.append("")

    for _, r in walk_df.sort_values(["stop_mode","stop_value","test_year"]).iterrows():
        report.append(
            f"{r['stop_mode']:<10} {r['stop_value']:>5.2f} | "
            f"train<= {int(r['train_end_year'])} PF {r['train_profit_factor']:.2f} "
            f"avg {r['train_avg_net_pips']:+.2f}p n={int(r['train_trades'])} -> "
            f"TEST {int(r['test_year'])}: "
            f"avg {r['test_avg_net_pips']:+.2f}p PF {r['test_profit_factor']:.2f} "
            f"n={int(r['test_trades'])} | "
            f"{'PASS' if r['test_positive'] else 'FAIL'}"
        )

    report.append("")
    report.append("ROBUSTNESS SCORECARD")
    report.append("-"*124)

    for _, r in score_df.iterrows():
        report.append(
            f"{'PASS' if r['ROBUSTNESS_PASS'] else 'FAIL':<4} | "
            f"{r['stop_mode']:<10} {r['stop_value']:>5.2f} | "
            f"PF {r['profit_factor']:.2f} | avg {r['avg_net_pips']:+.2f}p | "
            f"positive years {int(r['positive_years'])}/{int(r['positive_years']+r['negative_years'])} | "
            f"walk-forward {int(r['walk_forward_positive'])}/{int(r['walk_forward_tests'])}"
        )

    report.append("")
    report.append("DECISION STANDARD")
    report.append("-"*124)
    report.append(
        "v28 is deliberately trying to disprove the v27 edge. "
        "The strategy is much more credible if several nearby stops pass, "
        "both directions contribute, and most walk-forward years remain positive."
    )
    report.append(
        "If performance is concentrated in one year, one direction, one month, "
        "or one isolated stop, do NOT proceed to live forward testing."
    )
    report.append(
        "If the edge survives this torture test, the next step should be a final MT5 EA "
        "implementing the frozen rules, followed by broker Strategy Tester and live demo forward testing."
    )

    (outdir/"v28_report.txt").write_text("\n".join(report), encoding="utf-8")

    print("\n" + "="*124)
    print("V28 COMPLETE")
    print("="*124)
    print("Output folder:", outdir.resolve())
    print("\nPaste v28_report.txt here.")
    print("If the report is strong, we are done searching and should code the final EA.")


if __name__ == "__main__":
    main()
