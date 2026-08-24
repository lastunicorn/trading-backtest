#!/usr/bin/env python3
"""
Candle DNA v27 — Narrow Asia Fade Execution / Expectancy Lab
============================================================

Purpose
-------
Turn the stable v25/v26/v26.1 behavior into an ACTUAL trade simulation.

Research basis
--------------
Observed behavior from prior local research:
- Narrow Asia threshold from discovery Q1 was about <= 21.72 pips.
- First London break of Asia reverted to Asia midpoint about 60-62%.
- Relative volume >= 1.6 lifted midpoint reversion into the upper-60s.
- Early breaks (roughly <=20 minutes) also modestly improved reversion.
- Successful reversions had much smaller adverse excursion than failures.

v27 stops asking "does midpoint get reached?"
and asks:

    "Can we trade this behavior profitably after realistic costs?"

Trade direction
---------------
If Asia HIGH breaks first:
    FADE SHORT toward Asia midpoint.

If Asia LOW breaks first:
    FADE LONG toward Asia midpoint.

Entry modes
-----------
1) ENTRY_BOUNDARY_REENTRY
   Wait for the first breakout, then wait for price to cross BACK through the
   broken Asia boundary. Enter at the boundary.

2) ENTRY_BREAK_CANDLE_CLOSE_REJECT
   Enter at breakout candle close ONLY if that breakout candle closed back inside Asia.

3) ENTRY_FIXED_OUTSIDE
   Fade at a fixed number of pips OUTSIDE the Asia boundary after the first break.
   Example: 2 pips outside Asia high -> short entry there.

4) ENTRY_IMMEDIATE_BOUNDARY
   Enter at the Asia boundary as soon as the first break occurs.
   Included mainly as a benchmark; 5m OHLC means exact intrabar execution is approximate.

Target
------
Default target is Asia midpoint.

Optional target modes:
- Asia midpoint
- fixed R multiple
- fixed pips

Stop modes
----------
A) Fixed pips:
   3 / 4 / 5 / 6 / 7 / 8 / 10 / 12 / 15 pips

B) Dynamic Asia range multiple:
   0.25 / 0.33 / 0.40 / 0.50 / 0.60 / 0.75 / 1.00 x Asia range

Filters
-------
- None
- relative volume >= 1.6
- first break <= 20 minutes after London open
- relative volume >= 1.6 AND break <= 20 minutes

Optional additional limits:
- max penetration at breakout
- require breakout candle rejection

Costs
-----
Default research friction:
    spread = 1.0 pip
    commission equivalent = 0.7 pip
    total = 1.7 pips per completed trade

Cost is subtracted from net trade P/L.

Chronological methodology
-------------------------
60% discovery
20% validation
20% untouched final test

A configuration is ROBUST only if:
- discovery expectancy > 0
- validation expectancy > 0
- final expectancy > 0

Outputs
-------
narrow_asia_v27_output/
    v27_report.txt
    v27_all_configs.csv
    v27_robust_configs.csv
    v27_best_trade_log.csv
    v27_best_annual_breakdown.csv
    v27_best_split_summary.csv
    v27_entry_mode_summary.csv
    v27_stop_mode_summary.csv

Run
---
python eurusd_narrow_asia_fade_v27.py ^
  "research_output_v24_1\EURUSD_M5_CLEAN_2020_2026.csv"

Optional:
python eurusd_narrow_asia_fade_v27.py ^
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
COST_PIPS = 1.7

ENTRY_MODES = [
    "BOUNDARY_REENTRY",
    "BREAK_CANDLE_CLOSE_REJECT",
    "FIXED_OUTSIDE",
    "IMMEDIATE_BOUNDARY",
]

FILTER_MODES = [
    "NONE",
    "RELVOL_1_6",
    "BREAK_20M",
    "RELVOL_1_6_AND_BREAK_20M",
]

FIXED_STOPS = [3,4,5,6,7,8,10,12,15]
RANGE_STOP_MULTS = [0.25,0.33,0.40,0.50,0.60,0.75,1.00]

FIXED_OUTSIDE_ENTRIES = [0.5,1.0,1.5,2.0,3.0,5.0]

MAX_BREAK_PEN_OPTIONS = [None, 1.0, 2.0, 3.0]

MIN_DISC_TRADES = 80
MIN_VAL_TRADES = 25
MIN_TEST_TRADES = 25


def parse_hhmm(s):
    h,m = s.strip().split(":")
    return int(h), int(m)


def mod(h,m):
    return h*60+m


def load_data(path):
    df = pd.read_csv(path)

    required = {"datetime","open","high","low","close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime","open","high","low","close"]).copy()
    df = df.sort_values("datetime").drop_duplicates("datetime").reset_index(drop=True)

    for c in ["open","high","low","close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    if "tick_volume" in df.columns:
        df["volume_proxy"] = pd.to_numeric(df["tick_volume"], errors="coerce")
    elif "volume" in df.columns:
        df["volume_proxy"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume_proxy"] = np.nan

    df["date"] = df["datetime"].dt.date
    df["weekday"] = df["datetime"].dt.dayofweek
    df["minute_of_day"] = df["datetime"].dt.hour*60 + df["datetime"].dt.minute

    df = df[df["weekday"] < 5].copy().reset_index(drop=True)

    volma = df["volume_proxy"].rolling(20).mean()
    df["relvol20"] = np.where(volma > 0, df["volume_proxy"]/volma, np.nan)

    return df


def split_dates(dates):
    dates = sorted(dates)
    n = len(dates)
    a = int(n*0.60)
    b = int(n*0.80)
    return set(dates[:a]), set(dates[a:b]), set(dates[b:])


def asia_stats(day, asia_start, asia_end):
    g = day[
        (day["minute_of_day"] >= asia_start)
        & (day["minute_of_day"] < asia_end)
    ]
    expected = max((asia_end-asia_start)//5, 1)

    if len(g) < expected-3:
        return None

    hi = float(g["high"].max())
    lo = float(g["low"].min())

    if not np.isfinite(hi) or not np.isfinite(lo) or hi <= lo:
        return None

    return {
        "high": hi,
        "low": lo,
        "mid": (hi+lo)/2.0,
        "range_pips": (hi-lo)/PIP,
    }


def build_day_ranges(df, asia_start, asia_end):
    rows = []
    for date, day in df.groupby("date"):
        day = day.copy().reset_index(drop=True)
        a = asia_stats(day, asia_start, asia_end)
        if a is None:
            continue
        rows.append({"date":date, "asia_range_pips":a["range_pips"]})
    return pd.DataFrame(rows)


def first_break(day, asia_hi, asia_lo, london_open, study_end):
    w = day[
        (day["minute_of_day"] >= london_open)
        & (day["minute_of_day"] <= study_end)
    ]

    for idx,r in w.iterrows():
        up = r["high"] >= asia_hi
        dn = r["low"] <= asia_lo

        if up and dn:
            return {"ambiguous":1}

        if up:
            return {
                "ambiguous":0,
                "idx":idx,
                "side":"HIGH",
                "break_minute":int(r["minute_of_day"]),
                "break_relvol20":float(r["relvol20"]) if np.isfinite(r["relvol20"]) else np.nan,
                "penetration_pips":(float(r["high"])-asia_hi)/PIP,
                "close_back_inside":int(float(r["close"]) < asia_hi),
            }

        if dn:
            return {
                "ambiguous":0,
                "idx":idx,
                "side":"LOW",
                "break_minute":int(r["minute_of_day"]),
                "break_relvol20":float(r["relvol20"]) if np.isfinite(r["relvol20"]) else np.nan,
                "penetration_pips":(asia_lo-float(r["low"]))/PIP,
                "close_back_inside":int(float(r["close"]) > asia_lo),
            }

    return None


def passes_filter(info, london_open, filter_mode):
    mins = info["break_minute"] - london_open
    rel = info["break_relvol20"]

    if filter_mode == "NONE":
        return True
    if filter_mode == "RELVOL_1_6":
        return np.isfinite(rel) and rel >= 1.6
    if filter_mode == "BREAK_20M":
        return mins <= 20
    if filter_mode == "RELVOL_1_6_AND_BREAK_20M":
        return np.isfinite(rel) and rel >= 1.6 and mins <= 20

    return False


def get_entry(day, info, asia_hi, asia_lo, entry_mode, outside_pips, study_end):
    idx = info["idx"]
    side = info["side"]
    first = day.loc[idx]

    if entry_mode == "BREAK_CANDLE_CLOSE_REJECT":
        if not info["close_back_inside"]:
            return None
        entry = float(first["close"])
        return {
            "entry": entry,
            "entry_idx": idx,
            "entry_minute": int(first["minute_of_day"]),
        }

    if entry_mode == "IMMEDIATE_BOUNDARY":
        entry = asia_hi if side=="HIGH" else asia_lo
        return {
            "entry": entry,
            "entry_idx": idx,
            "entry_minute": int(first["minute_of_day"]),
        }

    if entry_mode == "FIXED_OUTSIDE":
        if side=="HIGH":
            target_entry = asia_hi + outside_pips*PIP
            path = day.loc[idx:].copy()
            path = path[path["minute_of_day"] <= study_end]
            for j,r in path.iterrows():
                if r["high"] >= target_entry:
                    return {
                        "entry": target_entry,
                        "entry_idx": j,
                        "entry_minute": int(r["minute_of_day"]),
                    }
        else:
            target_entry = asia_lo - outside_pips*PIP
            path = day.loc[idx:].copy()
            path = path[path["minute_of_day"] <= study_end]
            for j,r in path.iterrows():
                if r["low"] <= target_entry:
                    return {
                        "entry": target_entry,
                        "entry_idx": j,
                        "entry_minute": int(r["minute_of_day"]),
                    }
        return None

    if entry_mode == "BOUNDARY_REENTRY":
        path = day.loc[idx:].copy()
        path = path[path["minute_of_day"] <= study_end]

        # Start from the NEXT bar to avoid impossible same-bar path assumptions.
        path = path.iloc[1:]

        if side=="HIGH":
            for j,r in path.iterrows():
                if r["low"] <= asia_hi:
                    return {
                        "entry": asia_hi,
                        "entry_idx": j,
                        "entry_minute": int(r["minute_of_day"]),
                    }
        else:
            for j,r in path.iterrows():
                if r["high"] >= asia_lo:
                    return {
                        "entry": asia_lo,
                        "entry_idx": j,
                        "entry_minute": int(r["minute_of_day"]),
                    }
        return None

    return None


def stop_price(side, entry, asia_range_pips, stop_mode, stop_value):
    if stop_mode == "FIXED":
        dist_pips = stop_value
    else:
        dist_pips = asia_range_pips * stop_value

    if side=="HIGH": # short
        return entry + dist_pips*PIP, dist_pips
    else:            # long
        return entry - dist_pips*PIP, dist_pips


def simulate_trade(day, info, entry_info, asia_mid, stop_mode, stop_value, asia_range_pips, study_end):
    side = info["side"]
    entry = entry_info["entry"]
    entry_idx = entry_info["entry_idx"]

    stop, stop_pips = stop_price(
        side, entry, asia_range_pips, stop_mode, stop_value
    )

    # Midpoint target.
    target = asia_mid

    if side=="HIGH":
        gross_reward_pips = (entry-target)/PIP
    else:
        gross_reward_pips = (target-entry)/PIP

    # If entry is already beyond midpoint in the wrong geometry, skip.
    if gross_reward_pips <= 0 or stop_pips <= 0:
        return None

    path = day.loc[entry_idx:].copy()
    path = path[path["minute_of_day"] <= study_end]

    # To avoid same-bar hindsight, resolve from next bar for non-close entries.
    if len(path) > 1:
        path_eval = path.iloc[1:].copy()
    else:
        path_eval = path.iloc[0:0].copy()

    exit_reason = "TIME"
    exit_price = float(path.iloc[-1]["close"]) if len(path) else entry

    for _,r in path_eval.iterrows():
        h = float(r["high"])
        l = float(r["low"])

        if side=="HIGH": # short
            hit_sl = h >= stop
            hit_tp = l <= target
        else: # long
            hit_sl = l <= stop
            hit_tp = h >= target

        if hit_sl and hit_tp:
            exit_reason = "SL"
            exit_price = stop
            break
        if hit_sl:
            exit_reason = "SL"
            exit_price = stop
            break
        if hit_tp:
            exit_reason = "TP"
            exit_price = target
            break

    if side=="HIGH":
        gross_pips = (entry-exit_price)/PIP
    else:
        gross_pips = (exit_price-entry)/PIP

    net_pips = gross_pips - COST_PIPS
    net_r = net_pips / stop_pips

    return {
        "entry": entry,
        "stop": stop,
        "target": target,
        "stop_pips": stop_pips,
        "gross_reward_to_mid_pips": gross_reward_pips,
        "exit_reason": exit_reason,
        "gross_pips": gross_pips,
        "net_pips": net_pips,
        "net_r": net_r,
        "win": int(net_pips > 0),
    }


def max_drawdown(values):
    a=np.asarray(values,dtype=float)
    if len(a)==0:
        return np.nan
    eq=np.concatenate([[0.0],np.cumsum(a)])
    peak=np.maximum.accumulate(eq)
    return float(np.max(peak-eq))


def max_consecutive_losses(values):
    max_run=0
    cur=0
    for x in values:
        if x < 0:
            cur += 1
            max_run=max(max_run,cur)
        else:
            cur=0
    return max_run


def summarize(trades):
    if len(trades)==0:
        return {}

    g=pd.DataFrame(trades)
    pnl=g["net_pips"].to_numpy(float)

    wins=g[g["net_pips"]>0]
    losses=g[g["net_pips"]<=0]

    gross_profit=wins["net_pips"].sum() if len(wins) else 0.0
    gross_loss=-losses["net_pips"].sum() if len(losses) else 0.0

    return {
        "trades":len(g),
        "win_rate":float((g["net_pips"]>0).mean()),
        "avg_net_pips":float(g["net_pips"].mean()),
        "median_net_pips":float(g["net_pips"].median()),
        "total_net_pips":float(g["net_pips"].sum()),
        "avg_net_r":float(g["net_r"].mean()),
        "profit_factor":float(gross_profit/gross_loss) if gross_loss>0 else np.inf,
        "avg_win_pips":float(wins["net_pips"].mean()) if len(wins) else np.nan,
        "avg_loss_pips":float(losses["net_pips"].mean()) if len(losses) else np.nan,
        "max_drawdown_pips":max_drawdown(pnl),
        "max_consecutive_losses":max_consecutive_losses(pnl),
        "tp_rate":float((g["exit_reason"]=="TP").mean()),
        "sl_rate":float((g["exit_reason"]=="SL").mean()),
        "time_exit_rate":float((g["exit_reason"]=="TIME").mean()),
    }


def build_daily_cache(df):
    return {d:g.copy().reset_index(drop=True) for d,g in df.groupby("date")}


def build_events(df, narrow_threshold, asia_start, asia_end, london_open, study_end):
    rows=[]

    for date, day in df.groupby("date"):
        day=day.copy().reset_index(drop=True)

        a=asia_stats(day,asia_start,asia_end)
        if a is None or a["range_pips"] > narrow_threshold:
            continue

        info=first_break(day,a["high"],a["low"],london_open,study_end)
        if info is None or info.get("ambiguous",0):
            continue

        rows.append({
            "date":date,
            "asia_high":a["high"],
            "asia_low":a["low"],
            "asia_mid":a["mid"],
            "asia_range_pips":a["range_pips"],
            **info,
        })

    return pd.DataFrame(rows)


def split_label(date,disc,val,test):
    if date in disc:return "DISC"
    if date in val:return "VAL"
    if date in test:return "TEST"
    return "OTHER"


def run_config(events, cache, config, london_open, study_end, disc, val, test, return_log=False):
    buckets={"DISC":[],"VAL":[],"TEST":[]}
    logs=[]

    for _,e in events.iterrows():
        if config["max_break_pen"] is not None and e["penetration_pips"] > config["max_break_pen"]:
            continue

        if not passes_filter(e,london_open,config["filter_mode"]):
            continue

        day=cache[e["date"]]

        entry_info=get_entry(
            day,
            e,
            e["asia_high"],
            e["asia_low"],
            config["entry_mode"],
            config["outside_pips"],
            study_end
        )

        if entry_info is None:
            continue

        tr=simulate_trade(
            day,
            e,
            entry_info,
            e["asia_mid"],
            config["stop_mode"],
            config["stop_value"],
            e["asia_range_pips"],
            study_end
        )

        if tr is None:
            continue

        split=split_label(e["date"],disc,val,test)

        rec={
            "date":e["date"],
            "split":split,
            "break_side":e["side"],
            "break_minutes_after_london":e["break_minute"]-london_open,
            "break_relvol20":e["break_relvol20"],
            "break_penetration_pips":e["penetration_pips"],
            "close_back_inside":e["close_back_inside"],
            "asia_range_pips":e["asia_range_pips"],
            "entry_mode":config["entry_mode"],
            "filter_mode":config["filter_mode"],
            "stop_mode":config["stop_mode"],
            "stop_value":config["stop_value"],
            "outside_pips":config["outside_pips"],
            "max_break_pen":config["max_break_pen"],
            **tr,
        }

        buckets[split].append(rec)
        logs.append(rec)

    summaries={k:summarize(v) for k,v in buckets.items()}

    if return_log:
        return summaries, pd.DataFrame(logs)

    return summaries


def config_grid():
    configs=[]

    for entry_mode in ENTRY_MODES:
        outside_values = FIXED_OUTSIDE_ENTRIES if entry_mode=="FIXED_OUTSIDE" else [0.0]

        for outside in outside_values:
            for filt in FILTER_MODES:
                for maxpen in MAX_BREAK_PEN_OPTIONS:

                    for stop in FIXED_STOPS:
                        configs.append({
                            "entry_mode":entry_mode,
                            "outside_pips":outside,
                            "filter_mode":filt,
                            "max_break_pen":maxpen,
                            "stop_mode":"FIXED",
                            "stop_value":float(stop),
                        })

                    for mult in RANGE_STOP_MULTS:
                        configs.append({
                            "entry_mode":entry_mode,
                            "outside_pips":outside,
                            "filter_mode":filt,
                            "max_break_pen":maxpen,
                            "stop_mode":"RANGE_MULT",
                            "stop_value":float(mult),
                        })

    return configs


def annual_breakdown(log):
    if len(log)==0:
        return pd.DataFrame()

    x=log.copy()
    x["year"]=pd.to_datetime(x["date"]).dt.year

    rows=[]
    for year,g in x.groupby("year"):
        s=summarize(g.to_dict("records"))
        rows.append({"year":int(year),**s})

    return pd.DataFrame(rows)


def group_summary(df,col):
    rows=[]
    if len(df)==0:
        return pd.DataFrame()

    for val,g in df.groupby(col):
        rows.append({
            col:val,
            "configs":len(g),
            "robust_configs":int(g["ROBUST"].sum()),
            "median_DISC_expectancy":g["DISC_avg_net_pips"].median(),
            "median_VAL_expectancy":g["VAL_avg_net_pips"].median(),
            "median_TEST_expectancy":g["TEST_avg_net_pips"].median(),
            "best_TEST_expectancy":g["TEST_avg_net_pips"].max(),
        })
    return pd.DataFrame(rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--out",default="narrow_asia_v27_output")
    ap.add_argument("--asia-start",default="02:00")
    ap.add_argument("--asia-end",default="10:00")
    ap.add_argument("--london-open",default="10:00")
    ap.add_argument("--study-end",default="14:00")
    args=ap.parse_args()

    outdir=Path(args.out)
    outdir.mkdir(parents=True,exist_ok=True)

    ah,am=parse_hhmm(args.asia_start)
    aeh,aem=parse_hhmm(args.asia_end)
    lh,lm=parse_hhmm(args.london_open)
    sh,sm=parse_hhmm(args.study_end)

    asia_start=mod(ah,am)
    asia_end=mod(aeh,aem)
    london_open=mod(lh,lm)
    study_end=mod(sh,sm)

    print("="*122)
    print("CANDLE DNA v27 — NARROW ASIA FADE EXECUTION / EXPECTANCY LAB")
    print("="*122)
    print("Loading:",args.csv)

    df=load_data(args.csv)
    cache=build_daily_cache(df)

    day_ranges=build_day_ranges(df,asia_start,asia_end)
    dates=sorted(day_ranges["date"].unique())
    disc,val,test=split_dates(dates)

    disc_ranges=day_ranges[
        day_ranges["date"].isin(disc)
    ]["asia_range_pips"].dropna()

    narrow_threshold=float(disc_ranges.quantile(0.25))
    print(f"Frozen narrow-Asia threshold: <= {narrow_threshold:.2f} pips")

    events=build_events(
        df,narrow_threshold,asia_start,asia_end,london_open,study_end
    )

    print(
        f"First-break events: {len(events)} | "
        f"DISC {events['date'].isin(disc).sum()} | "
        f"VAL {events['date'].isin(val).sum()} | "
        f"TEST {events['date'].isin(test).sum()}"
    )

    configs=config_grid()
    print(f"Configurations: {len(configs)}")

    rows=[]

    for i,cfg in enumerate(configs,1):
        if i==1 or i%250==0:
            print(f"Config {i}/{len(configs)}")

        s=run_config(
            events,cache,cfg,london_open,study_end,disc,val,test
        )

        d=s["DISC"]; v=s["VAL"]; t=s["TEST"]

        if not d or not v or not t:
            continue

        robust=(
            d["trades"]>=MIN_DISC_TRADES
            and v["trades"]>=MIN_VAL_TRADES
            and t["trades"]>=MIN_TEST_TRADES
            and d["avg_net_pips"]>0
            and v["avg_net_pips"]>0
            and t["avg_net_pips"]>0
        )

        rows.append({
            **cfg,

            "DISC_trades":d["trades"],
            "DISC_win_rate":d["win_rate"],
            "DISC_avg_net_pips":d["avg_net_pips"],
            "DISC_total_net_pips":d["total_net_pips"],
            "DISC_profit_factor":d["profit_factor"],
            "DISC_avg_net_r":d["avg_net_r"],
            "DISC_max_dd_pips":d["max_drawdown_pips"],

            "VAL_trades":v["trades"],
            "VAL_win_rate":v["win_rate"],
            "VAL_avg_net_pips":v["avg_net_pips"],
            "VAL_total_net_pips":v["total_net_pips"],
            "VAL_profit_factor":v["profit_factor"],
            "VAL_avg_net_r":v["avg_net_r"],
            "VAL_max_dd_pips":v["max_drawdown_pips"],

            "TEST_trades":t["trades"],
            "TEST_win_rate":t["win_rate"],
            "TEST_avg_net_pips":t["avg_net_pips"],
            "TEST_total_net_pips":t["total_net_pips"],
            "TEST_profit_factor":t["profit_factor"],
            "TEST_avg_net_r":t["avg_net_r"],
            "TEST_max_dd_pips":t["max_drawdown_pips"],
            "TEST_max_consecutive_losses":t["max_consecutive_losses"],

            "ROBUST":robust,
        })

    results=pd.DataFrame(rows)

    if len(results)==0:
        raise RuntimeError("No configurations produced usable split results.")

    results["stability_spread_pips"] = (
        results[["DISC_avg_net_pips","VAL_avg_net_pips","TEST_avg_net_pips"]].max(axis=1)
        - results[["DISC_avg_net_pips","VAL_avg_net_pips","TEST_avg_net_pips"]].min(axis=1)
    )

    results["score"] = (
        results["TEST_avg_net_pips"]
        + results["VAL_avg_net_pips"]
        + 0.5*results["DISC_avg_net_pips"]
        - 0.15*results["stability_spread_pips"]
    )

    results=results.sort_values(
        ["ROBUST","score","TEST_profit_factor","TEST_trades"],
        ascending=[False,False,False,False]
    )

    robust=results[results["ROBUST"]==True].copy()

    results.to_csv(outdir/"v27_all_configs.csv",index=False)
    robust.to_csv(outdir/"v27_robust_configs.csv",index=False)

    # Analyze best robust config; if none, analyze best overall.
    best = robust.iloc[0] if len(robust) else results.iloc[0]

    cfg={
        "entry_mode":best["entry_mode"],
        "outside_pips":float(best["outside_pips"]),
        "filter_mode":best["filter_mode"],
        "max_break_pen":None if pd.isna(best["max_break_pen"]) else float(best["max_break_pen"]),
        "stop_mode":best["stop_mode"],
        "stop_value":float(best["stop_value"]),
    }

    best_summaries,best_log=run_config(
        events,cache,cfg,london_open,study_end,disc,val,test,return_log=True
    )

    best_log.to_csv(outdir/"v27_best_trade_log.csv",index=False)

    annual=annual_breakdown(best_log)
    annual.to_csv(outdir/"v27_best_annual_breakdown.csv",index=False)

    split_rows=[]
    for split,s in best_summaries.items():
        if s:
            split_rows.append({"split":split,**s})
    split_df=pd.DataFrame(split_rows)
    split_df.to_csv(outdir/"v27_best_split_summary.csv",index=False)

    entry_summary=group_summary(results,"entry_mode")
    stop_summary=group_summary(results,"stop_mode")
    entry_summary.to_csv(outdir/"v27_entry_mode_summary.csv",index=False)
    stop_summary.to_csv(outdir/"v27_stop_mode_summary.csv",index=False)

    report=[]
    report.append("CANDLE DNA v27 — NARROW ASIA FADE EXECUTION / EXPECTANCY LAB")
    report.append("="*122)
    report.append("")
    report.append(f"Frozen narrow-Asia threshold: <= {narrow_threshold:.2f} pips")
    report.append(f"First-break events: {len(events)}")
    report.append(f"Cost model: {COST_PIPS:.1f} pips per completed trade")
    report.append(f"Configurations tested: {len(results)}")
    report.append(f"ROBUST configurations: {len(robust)}")
    report.append("")

    report.append("BEST ROBUST CONFIGURATIONS")
    report.append("-"*122)

    top = robust.head(30) if len(robust) else results.head(30)

    if len(robust)==0:
        report.append("No configuration was positive in discovery, validation, and final test with required sample sizes.")
        report.append("Showing best overall configurations instead:")
        report.append("")

    for _,r in top.iterrows():
        maxpen = "None" if pd.isna(r["max_break_pen"]) else f"{r['max_break_pen']:.1f}p"

        report.append(
            f"{'ROBUST' if r['ROBUST'] else 'FAIL':<6} | "
            f"{r['entry_mode']:<24} | "
            f"filter {r['filter_mode']:<25} | "
            f"maxPen {maxpen:<6} | "
            f"SL {r['stop_mode']} {r['stop_value']:.2f} | "
            f"DISC {r['DISC_avg_net_pips']:+.2f}p PF {r['DISC_profit_factor']:.2f} "
            f"n={int(r['DISC_trades'])} | "
            f"VAL {r['VAL_avg_net_pips']:+.2f}p PF {r['VAL_profit_factor']:.2f} "
            f"n={int(r['VAL_trades'])} | "
            f"TEST {r['TEST_avg_net_pips']:+.2f}p PF {r['TEST_profit_factor']:.2f} "
            f"WR {r['TEST_win_rate']*100:5.1f}% n={int(r['TEST_trades'])}"
        )

    report.append("")
    report.append("BEST CONFIGURATION DETAIL")
    report.append("-"*122)
    report.append(f"Entry mode: {cfg['entry_mode']}")
    report.append(f"Outside entry pips: {cfg['outside_pips']}")
    report.append(f"Filter: {cfg['filter_mode']}")
    report.append(f"Max breakout penetration: {cfg['max_break_pen']}")
    report.append(f"Stop mode: {cfg['stop_mode']}")
    report.append(f"Stop value: {cfg['stop_value']}")
    report.append("")

    for _,r in split_df.iterrows():
        report.append(
            f"{r['split']:<5} | trades {int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | "
            f"PF {r['profit_factor']:.2f} | "
            f"avgR {r['avg_net_r']:+.3f} | "
            f"total {r['total_net_pips']:+.1f}p | "
            f"DD {r['max_drawdown_pips']:.1f}p | "
            f"max losses {int(r['max_consecutive_losses'])}"
        )

    report.append("")
    report.append("ANNUAL BREAKDOWN — BEST CONFIG")
    report.append("-"*122)

    for _,r in annual.iterrows():
        report.append(
            f"{int(r['year'])} | trades {int(r['trades']):>3} | "
            f"WR {r['win_rate']*100:5.1f}% | "
            f"avg {r['avg_net_pips']:+.2f}p | "
            f"PF {r['profit_factor']:.2f} | "
            f"total {r['total_net_pips']:+.1f}p | "
            f"DD {r['max_drawdown_pips']:.1f}p"
        )

    report.append("")
    report.append("INTERPRETATION")
    report.append("-"*122)
    report.append(
        "A useful result is not merely a high win rate. It should have positive expectancy and acceptable drawdown "
        "in discovery, validation, and untouched final test after the 1.7-pip cost assumption."
    )
    report.append(
        "If a robust region appears across multiple nearby stop sizes / entry modes, that is much stronger than one isolated best parameter."
    )
    report.append(
        "If no robust configuration survives, the narrow-Asia midpoint tendency is real but not necessarily monetizable with these entry/stop mechanics."
    )

    (outdir/"v27_report.txt").write_text("\n".join(report),encoding="utf-8")

    print("\n"+"="*122)
    print("V27 COMPLETE")
    print("="*122)
    print("Output folder:",outdir.resolve())
    print("\nPaste v27_report.txt here.")
    print("If robust configs exist, also paste v27_best_annual_breakdown.csv or upload it.")


if __name__=="__main__":
    main()
