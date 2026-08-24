#!/usr/bin/env python3
import argparse, csv, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PIP = 0.0001
COST_PIPS = 1.7
OUTPUT_DIR = "research_output"
M5_OUTPUT = "EURUSD_M5_LOCAL_2020_2026.csv"

RANGE_MINUTES = [30,45,60,75,90,120]
ENTRY_DELAYS = [0,5,10,15,30]
STOP_FRACTIONS = [0.40,0.50,0.60,0.67,0.75]
R_MULTIPLES = [1.0,1.5,2.0,2.5,3.0]

def parse_hhmm(s):
    h,m=s.strip().split(":")
    return int(h),int(m)

def sniff_sep(path):
    with open(path,"r",encoding="utf-8-sig",errors="ignore") as f:
        sample=f.read(4096)
    if "\t" in sample: return "\t"
    try: return csv.Sniffer().sniff(sample,delimiters=",;").delimiter
    except: return ","

def normalize_columns(df):
    df=df.rename(columns={c:str(c).strip() for c in df.columns})
    aliases={
        "<DATE>":"date","<TIME>":"clock","<OPEN>":"open","<HIGH>":"high",
        "<LOW>":"low","<CLOSE>":"close","<TICKVOL>":"tick_volume",
        "<VOL>":"volume","<SPREAD>":"spread",
        "DATE":"date","TIME":"clock","OPEN":"open","HIGH":"high",
        "LOW":"low","CLOSE":"close","TICKVOL":"tick_volume",
        "VOL":"volume","SPREAD":"spread"
    }
    df=df.rename(columns={k:v for k,v in aliases.items() if k in df.columns})

    if "time" in df.columns and "date" not in df.columns:
        df["datetime"]=pd.to_datetime(df["time"],errors="coerce")
    elif "date" in df.columns and "clock" in df.columns:
        df["datetime"]=pd.to_datetime(df["date"].astype(str)+" "+df["clock"].astype(str),errors="coerce")
    elif "datetime" in df.columns:
        df["datetime"]=pd.to_datetime(df["datetime"],errors="coerce")
    elif len(df.columns)>=2:
        df["datetime"]=pd.to_datetime(df.iloc[:,0].astype(str)+" "+df.iloc[:,1].astype(str),errors="coerce")

    for c in ["open","high","low","close"]:
        if c not in df.columns:
            raise ValueError(f"Missing {c}; found {list(df.columns)}")
        df[c]=pd.to_numeric(df[c],errors="coerce")
    for c in ["tick_volume","volume","spread"]:
        if c in df.columns:
            df[c]=pd.to_numeric(df[c],errors="coerce")
    return df

def load_and_resample_one(path):
    sep=sniff_sep(path)
    df=pd.read_csv(path,sep=sep,low_memory=False)
    df=normalize_columns(df)
    df=df.dropna(subset=["datetime","open","high","low","close"]).copy()
    df=df.sort_values("datetime").drop_duplicates("datetime",keep="last")
    if df.empty: return pd.DataFrame()

    df=df.set_index("datetime")
    agg={"open":"first","high":"max","low":"min","close":"last"}
    if "tick_volume" in df.columns: agg["tick_volume"]="sum"
    if "volume" in df.columns: agg["volume"]="sum"
    if "spread" in df.columns: agg["spread"]="mean"
    m5=df.resample("5min").agg(agg).dropna(subset=["open","high","low","close"]).reset_index()
    return m5

def build_m5(folder,outdir):
    files=sorted(folder.glob("*.csv"))
    files=[f for f in files if f.name.lower()!=M5_OUTPUT.lower() and "research_output" not in str(f).lower()]
    print(f"Found {len(files)} source CSV files.")
    pieces=[]; stats=[]
    for i,f in enumerate(files,1):
        print(f"[{i}/{len(files)}] {f.name}")
        try:
            m5=load_and_resample_one(f)
            if m5.empty:
                print("  no usable rows")
                continue
            pieces.append(m5)
            stats.append((f.name,len(m5),m5["datetime"].min(),m5["datetime"].max()))
            print(f"  {len(m5):,} M5 bars | {m5['datetime'].min()} -> {m5['datetime'].max()}")
        except Exception as e:
            print("  ERROR:",e)
    if not pieces:
        raise RuntimeError("No usable source files.")
    combined=pd.concat(pieces,ignore_index=True).sort_values("datetime")
    before=len(combined)
    combined=combined.drop_duplicates("datetime",keep="last").reset_index(drop=True)
    dupes=before-len(combined)
    out_path=outdir/M5_OUTPUT
    combined.to_csv(out_path,index=False)
    return combined,stats,dupes,out_path

def maxdd(vals):
    a=np.asarray(vals,float)
    if len(a)==0:return np.nan
    eq=np.concatenate([[0.0],np.cumsum(a)])
    peak=np.maximum.accumulate(eq)
    return float(np.max(peak-eq))

def prep_session(df):
    x=df.copy()
    x["datetime"]=pd.to_datetime(x["datetime"],errors="coerce")
    x=x.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)
    x["date"]=x["datetime"].dt.date
    x["minute_of_day"]=x["datetime"].dt.hour*60+x["datetime"].dt.minute
    x["weekday"]=x["datetime"].dt.dayofweek
    return x[x["weekday"]<5].copy()

def get_range(day,activation,minutes):
    g=day[(day["minute_of_day"]>=activation-minutes)&(day["minute_of_day"]<activation)]
    expected=minutes//5
    if len(g)<max(expected-1,1): return None
    hi=float(g["high"].max()); lo=float(g["low"].min())
    if not np.isfinite(hi) or not np.isfinite(lo) or hi<=lo:return None
    return hi,lo

def cost_r(risk_pips):
    return COST_PIPS/risk_pips if risk_pips>0 else np.nan

def simulate(day,activation,cutoff,rm,sf,rr):
    rg=get_range(day,activation,rm)
    if rg is None:return None
    hi,lo=rg; size=hi-lo
    le=hi; se=lo
    lsl=hi-sf*size; ssl=lo+sf*size
    lr=(le-lsl)/PIP; sr=(ssl-se)/PIP
    ltp=le+rr*(le-lsl); stp=se-rr*(ssl-se)
    w=day[(day["minute_of_day"]>=activation)&(day["minute_of_day"]<=cutoff)]
    if w.empty:return None

    active=None; result=0.0; triggered=0; side=""; first_bar=True
    for _,b in w.iterrows():
        h=float(b["high"]); l=float(b["low"])
        if active is None:
            up=h>=le; dn=l<=se
            if up and dn:return {"ambiguous":1}
            if up:
                active="LONG"; triggered=1; side="LONG"; first_bar=True
            elif dn:
                active="SHORT"; triggered=1; side="SHORT"; first_bar=True
            continue

        if active=="LONG":
            hs=l<=lsl; ht=h>=ltp
            if hs and ht or hs:
                result=-1.0-cost_r(lr); active=None; break
            if ht:
                result=rr-cost_r(lr); active=None; break
        else:
            hs=h>=ssl; ht=l<=stp
            if hs and ht or hs:
                result=-1.0-cost_r(sr); active=None; break
            if ht:
                result=rr-cost_r(sr); active=None; break

    if active is not None:
        last=w.iloc[-1]; px=float(last["close"])
        if active=="LONG":
            result=((px-le)/PIP)/lr-cost_r(lr)
        else:
            result=((se-px)/PIP)/sr-cost_r(sr)

    return {"ambiguous":0,"triggered":triggered,"side":side,"range_pips":size/PIP,"net_r":result}

def run_research(df,oh,om,ch,cm,outdir):
    x=prep_session(df)
    open_min=oh*60+om; cutoff=ch*60+cm
    days=sorted(x["date"].unique())
    a=int(len(days)*0.60); b=int(len(days)*0.80)
    disc=set(days[:a]); val=set(days[a:b]); test=set(days[b:])
    cache={d:g.reset_index(drop=True) for d,g in x.groupby("date")}

    rows=[]
    configs=[(rm,d,sf,rr) for rm in RANGE_MINUTES for d in ENTRY_DELAYS for sf in STOP_FRACTIONS for rr in R_MULTIPLES]
    print(f"Session research configurations: {len(configs)}")
    for i,(rm,delay,sf,rr) in enumerate(configs,1):
        if i==1 or i%100==0: print(f"Research {i}/{len(configs)}")
        buckets={"DISC":[],"VAL":[],"TEST":[]}
        activation=open_min+delay
        for d in days:
            r=simulate(cache[d],activation,cutoff,rm,sf,rr)
            if r is None or r.get("ambiguous",0): continue
            key="DISC" if d in disc else "VAL" if d in val else "TEST"
            buckets[key].append(r)
        row={"range_minutes":rm,"entry_delay_minutes":delay,"stop_fraction":sf,"reward_r":rr}
        for key,arr in buckets.items():
            vals=[z["net_r"] for z in arr]
            trades=[z for z in arr if z["triggered"]]
            row[f"{key}_days"]=len(arr)
            row[f"{key}_trades"]=len(trades)
            row[f"{key}_avg_net_r_day"]=np.mean(vals) if vals else np.nan
            row[f"{key}_total_net_r"]=np.sum(vals) if vals else np.nan
            row[f"{key}_profitable_day_rate"]=np.mean(np.asarray(vals)>0) if vals else np.nan
            row[f"{key}_max_dd_r"]=maxdd(vals) if vals else np.nan
        row["ROBUST"]=bool(
            np.isfinite(row["DISC_avg_net_r_day"]) and np.isfinite(row["VAL_avg_net_r_day"]) and np.isfinite(row["TEST_avg_net_r_day"])
            and row["DISC_avg_net_r_day"]>0 and row["VAL_avg_net_r_day"]>0 and row["TEST_avg_net_r_day"]>0
        )
        rows.append(row)

    grid=pd.DataFrame(rows).sort_values(
        ["ROBUST","TEST_avg_net_r_day","VAL_avg_net_r_day","DISC_avg_net_r_day"],
        ascending=[False,False,False,False]
    )
    grid.to_csv(outdir/"v24_range_grid.csv",index=False)

    rep=[]
    rep.append("V24 LOCAL SESSION / RANGE RESEARCH")
    rep.append("="*100)
    rep.append(f"Server-time session open: {oh:02d}:{om:02d}")
    rep.append(f"Server-time cutoff: {ch:02d}:{cm:02d}")
    rep.append(f"Trading days: {len(days)}")
    rep.append(f"Discovery/validation/final days: {len(disc)}/{len(val)}/{len(test)}")
    rep.append(f"Robust configs positive in all 3 splits: {int(grid['ROBUST'].sum())}")
    rep.append("")
    rep.append("TOP CONFIGURATIONS")
    rep.append("-"*100)
    for _,r in grid.head(25).iterrows():
        rep.append(
            f"{'ROBUST' if r['ROBUST'] else 'FAIL':<6} | range {int(r['range_minutes']):>3}m | "
            f"delay +{int(r['entry_delay_minutes']):>2}m | SL {r['stop_fraction']:.2f} | TP {r['reward_r']:.1f}R | "
            f"DISC {r['DISC_avg_net_r_day']:+.3f} | VAL {r['VAL_avg_net_r_day']:+.3f} | "
            f"TEST {r['TEST_avg_net_r_day']:+.3f} R/day | test trades {int(r['TEST_trades'])}"
        )
    (outdir/"v24_session_report.txt").write_text("\n".join(rep),encoding="utf-8")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--folder",default=".")
    ap.add_argument("--session-open",default="10:00",help="BROKER SERVER TIME")
    ap.add_argument("--cutoff",default="14:00",help="BROKER SERVER TIME")
    args=ap.parse_args()

    folder=Path(args.folder).resolve()
    outdir=folder/OUTPUT_DIR
    outdir.mkdir(exist_ok=True)

    oh,om=parse_hhmm(args.session_open)
    ch,cm=parse_hhmm(args.cutoff)

    print("="*100)
    print("EURUSD LOCAL RESEARCH BUILDER v24")
    print("="*100)
    print("Folder:",folder)

    m5,stats,dupes,out_path=build_m5(folder,outdir)

    quality=[
        "V24 DATA QUALITY","="*80,
        f"Source CSV files processed: {len(stats)}",
        f"Duplicate M5 timestamps removed: {dupes:,}",
        f"Final M5 bars: {len(m5):,}",
        f"First M5 candle: {m5['datetime'].min()}",
        f"Last M5 candle: {m5['datetime'].max()}",
        f"Saved M5 file: {out_path}",
        "","SOURCE FILE SUMMARY","-"*80
    ]
    for name,n,first,last in stats:
        quality.append(f"{name} | {n:,} bars | {first} -> {last}")
    (outdir/"v24_data_quality.txt").write_text("\n".join(quality),encoding="utf-8")

    run_research(m5,oh,om,ch,cm,outdir)

    print("\nDONE")
    print("Open:",outdir)
    print("Paste these into ChatGPT:")
    print("  v24_data_quality.txt")
    print("  v24_session_report.txt")
    print("No giant CSV upload needed.")

if __name__=="__main__":
    main()
