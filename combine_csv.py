import pandas as pd
import glob
import os

files = glob.glob("*.csv")
files = [f for f in files if f != "EURUSD_M5_2020_2026.csv"]

print(f"Found {len(files)} CSV files.")

frames = []

for i, file in enumerate(sorted(files), 1):
    print(f"[{i}/{len(files)}] Reading {file}")

    try:
        df = pd.read_csv(file, sep="\t")

        if len(df.columns) == 1:
            df = pd.read_csv(file)

        df["SOURCE_FILE"] = os.path.basename(file)
        frames.append(df)

    except Exception as e:
        print(f"ERROR reading {file}: {e}")

print("\nCombining...")

combined = pd.concat(frames, ignore_index=True)

if "<DATE>" in combined.columns and "<TIME>" in combined.columns:
    combined["_datetime"] = pd.to_datetime(
        combined["<DATE>"].astype(str) + " " +
        combined["<TIME>"].astype(str),
        errors="coerce"
    )

    combined = combined.sort_values("_datetime")

    before = len(combined)

    combined = combined.drop_duplicates(
        subset=["_datetime"],
        keep="last"
    )

    removed = before - len(combined)

    print(f"Removed {removed:,} duplicate candles.")

    print("\nDATA RANGE")
    print("First candle:", combined["_datetime"].min())
    print("Last candle: ", combined["_datetime"].max())

    combined = combined.drop(columns=["_datetime"])

else:
    print("\nWARNING: Could not find <DATE> and <TIME> columns.")
    print("Columns found:")
    print(list(combined.columns))

combined = combined.drop(columns=["SOURCE_FILE"])

combined.to_csv(
    "EURUSD_M5_2020_2026.csv",
    index=False
)

print("\nDONE")
print(f"Final candles: {len(combined):,}")
print("Created: EURUSD_M5_2020_2026.csv")