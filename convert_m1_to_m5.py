import pandas as pd

INPUT_FILE = "EURUSD_M5_2020_2026.csv"
OUTPUT_FILE = "EURUSD_M5_FINAL_2020_2026.csv"

print("Loading M1 data...")
print("This may take a little while because the file is very large.")

df = pd.read_csv(INPUT_FILE)

print(f"Loaded {len(df):,} rows")
print("Columns:", list(df.columns))

# MT5 export format
if "<DATE>" in df.columns and "<TIME>" in df.columns:

    df["datetime"] = pd.to_datetime(
        df["<DATE>"].astype(str) + " " +
        df["<TIME>"].astype(str),
        errors="coerce"
    )

    open_col = "<OPEN>"
    high_col = "<HIGH>"
    low_col = "<LOW>"
    close_col = "<CLOSE>"

    tickvol_col = "<TICKVOL>" if "<TICKVOL>" in df.columns else None
    vol_col = "<VOL>" if "<VOL>" in df.columns else None
    spread_col = "<SPREAD>" if "<SPREAD>" in df.columns else None

else:
    raise Exception(
        "Could not find MT5 <DATE> and <TIME> columns."
    )

df = df.dropna(subset=["datetime"])

df = df.sort_values("datetime")

# Remove duplicate M1 candles first
before = len(df)

df = df.drop_duplicates(
    subset=["datetime"],
    keep="last"
)

print(f"Removed {before - len(df):,} duplicate M1 rows")

df = df.set_index("datetime")

aggregation = {
    open_col: "first",
    high_col: "max",
    low_col: "min",
    close_col: "last",
}

if tickvol_col:
    aggregation[tickvol_col] = "sum"

if vol_col:
    aggregation[vol_col] = "sum"

if spread_col:
    aggregation[spread_col] = "mean"

print("Converting M1 -> M5...")

m5 = df.resample("5min").agg(aggregation)

# Remove periods where no market data existed
m5 = m5.dropna(
    subset=[
        open_col,
        high_col,
        low_col,
        close_col
    ]
)

m5 = m5.reset_index()

print("")
print("====================================")
print("M5 DATA CREATED")
print("====================================")
print(f"M1 candles: {len(df):,}")
print(f"M5 candles: {len(m5):,}")
print("")
print("First candle:", m5["datetime"].min())
print("Last candle: ", m5["datetime"].max())

m5.to_csv(
    OUTPUT_FILE,
    index=False
)

print("")
print("Saved:")
print(OUTPUT_FILE)
print("")
print("Done.")