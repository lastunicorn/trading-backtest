#!/usr/bin/env python3
"""
EURUSD Local Research Builder v24.1
Robust MT5 CSV loader for Windows folders containing many M1 exports.

Fixes:
- Handles MT5 files WITH headers.
- Handles MT5 files WITHOUT headers.
- Handles tab, comma, or semicolon separators.
- Skips previously generated/combined giant files.
- Converts each source file M1 -> M5 one at a time.
- De-duplicates overlapping months/years.
- Produces a small data-quality report first.

Run:
    python eurusd_local_research_v24_1.py

Optional:
    python eurusd_local_research_v24_1.py --session-open 10:00 --cutoff 14:00
"""

import argparse
import csv
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001
COST_PIPS = 1.7
OUTDIR_NAME = "research_output_v24_1"
M5_NAME = "EURUSD_M5_CLEAN_2020_2026.csv"

RANGE_MINUTES = [30,45,60,75,90,120]
ENTRY_DELAYS = [0,5,10,15,30]
STOP_FRACTIONS = [0.40,0.50,0.60,0.67,0.75]
R_MULTIPLES = [1.0,1.5,2.0,2.5,3.0]

SKIP_NAME_PARTS = [
    "EURUSD_M5_2020_2026",
    "EURUSD_M5_FINAL",
    "EURUSD_M5_LOCAL",
    "EURUSD_M5_CLEAN",
    "combined",
    "combine",
    "research_output",
    "v24_",
]

def parse_hhmm(s):
    h,m=s.split(":")
    return int(h),int(m)

def sniff_sep(path):
    with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
        sample=f.read(8192)
    if "\t" in sample:
        return "\t"
    counts={",":sample.count(","), ";":sample.count(";")}
    return max(counts,key=counts.get) if max(counts.values())>0 else "\t"

def first_line_tokens(path, sep):
    with open(path,"r",encoding="utf-8-sig",errors="ignore") as f:
        line=f.readline().strip()
    return [x.strip() for x in line.split(sep)]

def looks_like_header(tokens):
    joined=" ".join(tokens).upper()
    keys=["DATE","TIME","OPEN","HIGH","LOW","CLOSE","TICKVOL","SPREAD"]
    return sum(k in joined for k in keys)>=3

def read_mt5_file(path):
    sep=sniff_sep(path)
    tokens=first_line_tokens(path,sep)
    has_header=looks_like_header(tokens)

    if has_header:
        df=pd.read_csv(path,sep=sep,low_memory=False,encoding="utf-8-sig")
        df.columns=[str(c).strip().upper().replace("<","").replace(">","") for c in df.columns]
        ren={
            "DATE":"date","TIME":"clock","OPEN":"open","HIGH":"high",
            "LOW":"low","CLOSE":"close","TICKVOL":"tick_volume",
            "VOL":"volume","SPREAD":"spread"
        }
        df=df.rename(columns={c:ren[c] for c in df.columns if c in ren})
    else:
        # Standard MT5 bar export order:
        # DATE TIME OPEN HIGH LOW CLOSE TICKVOL VOL SPREAD
        raw=pd.read_csv(path,sep=sep,header=None,low_memory=False,encoding="utf-8-sig")
        n=raw.shape[1]

        if n >= 9:
            names=["date","clock","open","high","low","close","tick_volume","volume","spread"]
            raw=raw.iloc[:,:9]
        elif n == 8:
            names=["date","clock","open","high","low","close","tick_volume","spread"]
        elif n == 7:
            names=["date","clock","open","high","low","close","tick_volume"]
        elif n == 6:
            names=["date","clock","open","high","low","close"]
        else:
            raise ValueError(f"Unsupported headerless layout: {n} columns")
        raw.columns=names
        df=raw

    required=["date","clock","open","high","low","close"]
    missing=[c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing {missing}; columns={list(df.columns)}")

    df["datetime"]=pd.to_datetime(
        df["date"].astype(str).str.strip()+" "+df["clock"].astype(str).str.strip(),
        errors="coerce"
    )

    for c in ["open","high","low","close","tick_volume","volume","spread"]:
        if c in df.columns:
            df[c]=pd.to_numeric(df[c],errors="coerce")

    df=df.dropna(subset=["datetime","open","high","low","close"]).copy()
    df=df.sort_values("datetime").drop_duplicates("datetime",keep="last")

    return df

def resample_m5(df):
    if df.empty:
        return pd.DataFrame()

    x=df.set_index("datetime")
    agg={"open":"first","high":"max","low":"min","close":"last"}
    if "tick_volume" in x.columns: agg["tick_volume"]="sum"
    if "volume" in x.columns: agg["volume"]="sum"
    if "spread" in x.columns: agg["spread"]="mean"

    m5=x.resample("5min").agg(agg)
    m5=m5.dropna(subset=["open","high","low","close"]).reset_index()
    return m5

def select_sources(folder):
    files=[]
    for f in sorted(folder.glob("data/eurusd/1min/*.csv")):
        low=f.name.lower()
        if any(part.lower() in low for part in SKIP_NAME_PARTS):
            continue
        files.append(f)
    return files

def build_clean_m5(folder,outdir):
    files=select_sources(folder)
    print(f"\nFound {len(files)} candidate source CSV files.")

    pieces=[]
    stats=[]
    errors=[]

    for i,f in enumerate(files,1):
        print(f"[{i}/{len(files)}] {f.name}")
        try:
            src=read_mt5_file(f)
            m5=resample_m5(src)
            if m5.empty:
                print("    SKIP: no usable rows")
                errors.append((f.name,"no usable rows"))
                continue
            print(f"    OK: {len(src):,} source rows -> {len(m5):,} M5 bars")
            print(f"        {m5['datetime'].min()} -> {m5['datetime'].max()}")
            pieces.append(m5)
            stats.append((f.name,len(src),len(m5),m5["datetime"].min(),m5["datetime"].max()))
        except Exception as e:
            print(f"    ERROR: {e}")
            errors.append((f.name,str(e)))

    if not pieces:
        raise RuntimeError("No usable source files. See errors above.")

    print("\nCombining converted M5 pieces...")
    allm5=pd.concat(pieces,ignore_index=True).sort_values("datetime")
    before=len(allm5)
    allm5=allm5.drop_duplicates("datetime",keep="last").reset_index(drop=True)
    dupes=before-len(allm5)

    outpath=outdir/M5_NAME
    allm5.to_csv(outpath,index=False)

    return allm5,stats,errors,dupes,outpath

def maxdd(vals):
    a=np.asarray(vals,float)
    if len(a)==0:return np.nan
    eq=np.concatenate([[0.0],np.cumsum(a)])
    peak=np.maximum.accumulate(eq)
    return float(np.max(peak-eq))

def prep(df):
    x=df.copy()
    x["datetime"]=pd.to_datetime(x["datetime"],errors="coerce")
    x=x.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    x["date"]=x["datetime"].dt.date
    x["minute_of_day"]=x["datetime"].dt.hour*60+x["datetime"].dt.minute
    x["weekday"]=x["datetime"].dt.dayofweek
    return x[x["weekday"]<5].copy()

def get_range(day,act,mins):
    g=day[(day["minute_of_day"]>=act-mins)&(day["minute_of_day"]<act)]
    if len(g)<max(mins//5-1,1):return None
    hi=float(g["high"].max()); lo=float(g["low"].min())
    if hi<=lo:return None
    return hi,lo

def simulate(day,act,cutoff,rm,sf,rr):
    rg=get_range(day,act,rm)
    if rg is None:return None
    hi,lo=rg; size=hi-lo
    le,se=hi,lo
    lsl=hi-sf*size; ssl=lo+sf*size
    lr=(le-lsl)/PIP; sr=(ssl-se)/PIP
    if lr<=0 or sr<=0:return None
    ltp=le+rr*(le-lsl); stp=se-rr*(ssl-se)

    w=day[(day["minute_of_day"]>=act)&(day["minute_of_day"]<=cutoff)]
    if w.empty:return None

    active=None; result=0.0; trig=0
    for _,b in w.iterrows():
        h=float(b["high"]); l=float(b["low"])

        if active is None:
            up=h>=le; dn=l<=se
            if up and dn:return {"ambiguous":1}
            if up:
                active="LONG"; trig=1
            elif dn:
                active="SHORT"; trig=1
            continue

        if active=="LONG":
            hs=l<=lsl; ht=h>=ltp
            if hs:
                result=-1.0-COST_PIPS/lr; active=None; break
            if ht:
                result=rr-COST_PIPS/lr; active=None; break
        else:
            hs=h>=ssl; ht=l<=stp
            if hs:
                result=-1.0-COST_PIPS/sr; active=None; break
            if ht:
                result=rr-COST_PIPS/sr; active=None; break

    if active is not None:
        px=float(w.iloc[-1]["close"])
        if active=="LONG":
            result=((px-le)/PIP)/lr-COST_PIPS/lr
        else:
            result=((se-px)/PIP)/sr-COST_PIPS/sr

    return {"ambiguous":0,"triggered":trig,"net_r":result}

def run_grid(df,oh,om,ch,cm,outdir):
    x=prep(df)
    openmin=oh*60+om
    cutoff=ch*60+cm

    days=sorted(x["date"].unique())
    a=int(len(days)*.60); b=int(len(days)*.80)
    disc=set(days[:a]); val=set(days[a:b]); test=set(days[b:])
    cache={d:g.reset_index(drop=True) for d,g in x.groupby("date")}

    configs=[(rm,d,sf,rr) for rm in RANGE_MINUTES for d in ENTRY_DELAYS for sf in STOP_FRACTIONS for rr in R_MULTIPLES]
    print(f"\nRunning {len(configs)} session configurations...")

    rows=[]
    for i,(rm,delay,sf,rr) in enumerate(configs,1):
        if i==1 or i%100==0:print(f"  config {i}/{len(configs)}")
        buckets={"DISC":[],"VAL":[],"TEST":[]}
        act=openmin+delay
        for d in days:
            r=simulate(cache[d],act,cutoff,rm,sf,rr)
            if r is None or r.get("ambiguous",0):continue
            key="DISC" if d in disc else "VAL" if d in val else "TEST"
            buckets[key].append(r)

        row={"range_minutes":rm,"delay_minutes":delay,"stop_fraction":sf,"reward_r":rr}
        for k,arr in buckets.items():
            vals=[z["net_r"] for z in arr]
            trades=sum(z["triggered"] for z in arr)
            row[f"{k}_days"]=len(arr)
            row[f"{k}_trades"]=trades
            row[f"{k}_avg_r_day"]=np.mean(vals) if vals else np.nan
            row[f"{k}_total_r"]=np.sum(vals) if vals else np.nan
            row[f"{k}_prof_days"]=np.mean(np.array(vals)>0) if vals else np.nan
            row[f"{k}_dd_r"]=maxdd(vals) if vals else np.nan

        row["ROBUST"]=bool(
            np.isfinite(row["DISC_avg_r_day"]) and
            np.isfinite(row["VAL_avg_r_day"]) and
            np.isfinite(row["TEST_avg_r_day"]) and
            row["DISC_avg_r_day"]>0 and row["VAL_avg_r_day"]>0 and row["TEST_avg_r_day"]>0
        )
        rows.append(row)

    grid=pd.DataFrame(rows).sort_values(
        ["ROBUST","TEST_avg_r_day","VAL_avg_r_day","DISC_avg_r_day"],
        ascending=[False,False,False,False]
    )
    grid.to_csv(outdir/"v24_1_range_grid.csv",index=False)

    rep=[
        "V24.1 MULTI-YEAR SESSION RANGE RESEARCH",
        "="*105,
        f"Broker-server session open tested: {oh:02d}:{om:02d}",
        f"Cutoff: {ch:02d}:{cm:02d}",
        f"Trading days: {len(days)}",
        f"Discovery / validation / final: {len(disc)} / {len(val)} / {len(test)}",
        f"Robust configurations: {int(grid['ROBUST'].sum())}",
        "",
        "TOP 30 CONFIGURATIONS",
        "-"*105,
    ]

    for _,r in grid.head(30).iterrows():
        rep.append(
            f"{'ROBUST' if r['ROBUST'] else 'FAIL':<6} | "
            f"range {int(r['range_minutes']):3d}m | delay +{int(r['delay_minutes']):2d}m | "
            f"SL {r['stop_fraction']:.2f} | TP {r['reward_r']:.1f}R | "
            f"DISC {r['DISC_avg_r_day']:+.3f} | VAL {r['VAL_avg_r_day']:+.3f} | "
            f"TEST {r['TEST_avg_r_day']:+.3f} R/day | test trades {int(r['TEST_trades'])}"
        )

    (outdir/"v24_1_session_report.txt").write_text("\n".join(rep),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--folder",default=".")
    ap.add_argument("--session-open",default="10:00",help="BROKER SERVER TIME")
    ap.add_argument("--cutoff",default="14:00",help="BROKER SERVER TIME")
    args=ap.parse_args()

    folder=Path(args.folder).resolve()
    outdir=folder/OUTDIR_NAME
    outdir.mkdir(exist_ok=True)

    oh,om=parse_hhmm(args.session_open)
    ch,cm=parse_hhmm(args.cutoff)

    print("="*90)
    print("EURUSD LOCAL RESEARCH BUILDER v24.1")
    print("="*90)
    print("Source folder:",folder)

    m5,stats,errors,dupes,outpath=build_clean_m5(folder,outdir)

    q=[
        "V24.1 DATA QUALITY REPORT","="*90,
        f"Successful source files: {len(stats)}",
        f"Failed/skipped source files: {len(errors)}",
        f"Duplicate M5 timestamps removed: {dupes:,}",
        f"Final M5 candles: {len(m5):,}",
        f"First candle: {m5['datetime'].min()}",
        f"Last candle: {m5['datetime'].max()}",
        f"Clean M5 saved at: {outpath}",
        "","FAILED/SKIPPED FILES","-"*90
    ]
    for name,err in errors:
        q.append(f"{name} | {err}")
    q += ["","SUCCESSFUL FILES","-"*90]
    for name,n1,n5,first,last in stats:
        q.append(f"{name} | source {n1:,} -> M5 {n5:,} | {first} -> {last}")

    (outdir/"v24_1_data_quality.txt").write_text("\n".join(q),encoding="utf-8")

    print("\nClean M5 created:")
    print(outpath)
    print(f"Candles: {len(m5):,}")
    print(f"Dates: {m5['datetime'].min()} -> {m5['datetime'].max()}")
    print(f"Duplicates removed: {dupes:,}")

    run_grid(m5,oh,om,ch,cm,outdir)

    print("\nDONE.")
    print("Open:",outdir)
    print("Paste these two text files here:")
    print("  v24_1_data_quality.txt")
    print("  v24_1_session_report.txt")

if __name__=="__main__":
    main()
