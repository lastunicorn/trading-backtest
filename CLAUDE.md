# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A quantitative research log for **one** EURUSD intraday strategy ("Candle DNA — Narrow Asia London Fade"), not an application. Each `eurusd_*_vNN.py` file is a self-contained, immutable research stage: a numbered snapshot of what was known at that point. Later versions supersede earlier ones but the earlier ones are kept for provenance.

**Do not edit a completed vNN script to change its findings.** New analysis goes in a new version file (the established convention: `v26` → `v26_1` for a bugfix pass, `v27` → `v28` for a new question). The committed `*_output/` directories are the record of what each script produced; regenerating them changes history, so only do it deliberately.

## Reviewing requests

Before implementing a request as literally stated, check it against good practice, and say so if a better approach exists rather than silently building the literal ask. "Good" means:

- Easy for a human to read, easy to maintain long-term, easy to debug and extend.
- Leaves a seam where a future need is genuinely likely — a parameter, a hook, a clear boundary — without building the extension itself. A small amount of extra effort here is worth it; building the unrequested feature is not.

## Pipeline (strictly sequential)

```
data/eurusd/1min/EURUSD_YYYY_MM.csv     raw MT5 M1 exports, 84 monthly files (gitignored)
  └─ eurusd_local_research_v24_1.py     robust MT5 loader → M1→M5 → dedupe → data-quality report
     eurusd_local_research_v24_2.py     same study on the shared ports/ + domain/ loader
       └─ research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv   ← the canonical dataset
            ├─ eurusd_behavior_atlas_v25.py       behavior discovery (no optimization)
            ├─ eurusd_narrow_asia_reversion_v26.py / _v26_1.py  trajectory analysis
            ├─ eurusd_narrow_asia_fade_v27.py     trade simulation / expectancy grid
            └─ eurusd_narrow_asia_torture_v28.py  robustness of the frozen v27 strategy
```

Everything from v25 onward takes the clean M5 CSV as its single positional argument.

### Commands

```bash
# Stage 0 — rebuild the clean M5 dataset from raw MT5 exports (only if raw data changed)
python3 eurusd_local_research_v24_2.py --folder data/eurusd/1min --out research_output_v24_2
python3 eurusd_local_research_v24_2.py --clean-csv research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv

# Stages 1-4 — each writes CSVs + a <version>_report.txt into its own --out dir
python3 eurusd_behavior_atlas_v25.py       research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_reversion_v26_1.py research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_fade_v27.py     research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_torture_v28.py  research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
```

Use `python3`, not `python` — this machine has only `/usr/bin/python3` (3.12), so bare `python` fails with `command not found`. Inside an activated venv both names work.

Requires only `pandas` + `numpy`, installed in the repo-local venv at `.venv/` (gitignored). **Activate it before running anything:**

```bash
source .venv/bin/activate      # prompt gains (.venv); `python` and `python3` both work
```

Pinned versions live in `requirements.txt` (currently pandas 3.0.5, numpy 2.5.2 on Python 3.12.3). To rebuild the environment from scratch:

```bash
sudo apt install python3.12-venv    # one-time; the system Python is PEP 668 "externally managed"
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

There are no tests, no linter, no build. The unit of verification is the human-readable `*_report.txt`; read that first, drop into the supporting CSV only when a number needs explaining.

Session-window flags exist on every script (`--asia-start`, `--asia-end`, `--london-open`, `--study-end`, `--ny-open`, `--day-end`) and default to **broker server time**, not UTC or exchange time. Defaults: Asia 02:00–10:00, London open 10:00, study end 14:00.

## Tooling outside the pipeline

`ports/`, `domain/`, `application/`, `show_m1_csv.py`, `rebuild_clean_m5.py` and `resample_m1_to_m5.py` are **not** research stages. They are shared code: reading raw data, and building the clean dataset the pipeline consumes. They are versionless and freely editable — the immutability rule applies only to `eurusd_*_vNN.py`.

The split between the packages is the point of the layout:

- **`ports/`** knows *file formats*. A port parses records and stops — no cleaning, no deduplication, no resampling, whether it hands back `Bar` objects or a DataFrame. Most ports are **stdlib-only** (no pandas, no numpy), so they run in any sandbox as-is; `mt5_file_access.mt5_frame_reader` is the deliberate exception, using pandas to build the DataFrame directly instead of going through `Bar` + `domain/frames.py`.
- **`domain/`** knows *what the data should look like*: how bars collapse into a coarser timeframe, which of two rows claiming the same timestamp wins, what counts as a raw source file, what a quality report must account for. This is where pandas lives. It never reads or writes files.
- **`application/`** wires `ports/` and `domain/` into a whole task: read the raw exports, resample and merge, write the result, return the numbers a CLI prints. The I/O that `domain/` refuses lives here.

```
ports/mt5_file_access/mt5_reader.py       MT5 CSV → typed `Bar` objects (dt, OHLC, volumes, spread)  [stdlib]
ports/mt5_file_access/mt5_frame_reader.py MT5 CSV → pandas frame directly, same fields                [pandas]
domain/frames.py                          resample a frame to a coarser timeframe
domain/dataset.py                         folder of exports → one clean, deduplicated dataset
application/resample_use_case.py          folder of M1 exports → merged CSV on a coarser grid + report
show_m1_csv.py                            CLI that prints an export as an aligned table
rebuild_clean_m5.py                       CLI that rebuilds the clean M5 dataset (stage 0)
resample_m1_to_m5.py                      CLI that only resamples M1 -> M5 into one CSV
```

```python
from ports.mt5_file_access import read_bars, iter_bars   # short form (re-exported)

bars = read_bars(path)      # list[Bar] — fine for one monthly export (~31k bars)
for bar in iter_bars(path): # generator — constant memory; use on multi-million-row files
    ...
```

The reader detects the separator (comma/tab/semicolon) and handles both headerless exports and `<DATE>`-style MT5 headers. `strict=True` (default) raises `BarParseError` on a malformed line; `strict=False` skips it and reports via an `on_skip` callback. `detect_layout(path)` reports which fields an export carries without parsing it.

Everything after parsing is `domain/` — the loading half of `eurusd_local_research_v24_1.py`, extracted so tooling and future stages stop re-implementing it:

```python
from ports.mt5_file_access import read_frame
from domain.frames import resample_ohlc
from domain.dataset import build_clean_dataset

m5 = resample_ohlc(read_frame("data/eurusd/1min/EURUSD_2020_01.csv"), "M5")

dataset = build_clean_dataset("data/eurusd/1min", progress=print)  # all 84 exports
dataset.frame, dataset.stats, dataset.errors, dataset.duplicates_removed
dataset.timeframe                # "M5" — a report never has to be told the timeframe
```

`build_clean_dataset` returns data and never prints or writes — reporting belongs to the caller. `rebuild_clean_m5.py` is that caller:

```bash
python3 rebuild_clean_m5.py --folder data/eurusd/1min --out clean_m5_output
```

It writes the clean CSV plus a `data_quality.txt`. Point `--out` at a scratch directory unless you deliberately mean to regenerate the committed `research_output_v24_1/`. v24.1 keeps its own copy of the loader and is still the script of record for what produced that directory.

`eurusd_local_research_v24_2.py` is the research-stage counterpart: the *same* v24.1 study — stage-0 build plus the range/delay/stop/reward grid — with the private loader deleted in favour of `build_clean_dataset()`. Its grid half is carried over unchanged and reproduces v24.1's `range_grid.csv` and `session_report.txt` byte-for-byte on identical input (verified on a two-month subset). What it adds: unparsable source lines are counted in the quality report instead of vanishing, sorting is stable (see the `rebuild_clean_m5.py` gotcha below), `--out` is a free-standing path rather than a fixed directory inside `--folder`, and `--clean-csv` skips the rebuild to study an existing clean M5 file. Prefer v24.2 for new stage-0 runs; v24.1 stays untouched as the provenance of `research_output_v24_1/`.

`resample_m1_to_m5.py` is the same build with the reporting dropped — step 1 of `eurusd_local_research_v24_2.py` (read M1, resample, save) and nothing else. It writes one CSV and no quality report, defaulting to `data/eurusd/1min/` in and `data/eurusd/5min/EURUSD.csv` out, overwriting an existing file after printing an `INFO:` line:

```bash
python3 resample_m1_to_m5.py
python3 resample_m1_to_m5.py --timeframe M15 --out data/eurusd/15min/EURUSD.csv
```

Use it when you just want the dataset somewhere; use `rebuild_clean_m5.py` when you also want the `data_quality.txt` that accounts for skipped files and unparsable lines.

```bash
python3 show_m1_csv.py                       # first 20 bars of data/eurusd/1min/EURUSD_2020_01.csv
python3 show_m1_csv.py --tail --rows 5
python3 show_m1_csv.py --all | less
python3 show_m1_csv.py path/to/export.csv --decimals 3
```

`ports/`, `ports/mt5_file_access/`, `domain/` and `application/` are regular packages (each has an `__init__.py`), and the CLIs must stay at the repo root for `ports.*` / `domain.*` / `application.*` to resolve from any working directory.

## Methodology invariants

These hold across every script and are the point of the whole exercise — preserve them in any new version:

- **Chronological 60/20/20 split** into discovery / validation / final test (`split_dates()`). Never shuffle; dates are sorted and sliced.
- **Thresholds are fit on discovery days only, then frozen** for validation and test. The narrow-Asia definition (discovery Q1 of Asia range) froze at **≤ 21.72 pips** and every downstream script hardcodes or re-derives that same number.
- A finding is only reported as `STABLE` / `ROBUST` when it holds in all three splits. Single-split results are noise.
- `PIP = 0.0001`; `COST_PIPS = 1.7` (round-trip friction) is subtracted from every simulated trade before any statistic is computed.
- Ambiguous 5m bars (one bar touching both Asia high and Asia low) are excluded rather than guessed.

## The frozen strategy (v28) and its live implementations

Asia range ≤ 21.72 pips → on the first break of the Asia range after London open, with breakout-bar relative volume (SMA-20 of volume) ≥ 1.6, **fade back toward the Asia midpoint**: wait for price to cross back through the broken boundary, enter there, target midpoint, stop = 1.00 × Asia range. Result over 2020–2026: 207 trades, 72% WR, PF 1.37, +257.5 pips net.

Two ports of that exact rule set exist and **must stay in sync with each other and with the v28 parameters**:

- `Candle_DNA_Narrow_Asia_London_Fade_v1.mq5` — MT5 EA, broker-server hours as integers (`InpAsiaStartHour = 2`, `InpTradeEndHour = 14`).
- `pine version 6.txt` — TradingView Pine v6 strategy. Note it expresses the same windows as **Europe/London sessions `0000-0800` / `0800-1200`**, which is the deliberate re-mapping of the broker-server 02:00–10:00 / 10:00–14:00 windows. Changing a session in one file without re-deriving the other silently desynchronizes the backtests.

## Gotchas

- `eurusd_local_research_v24.py` and the ad-hoc `combine_csv.py` / `convert_m1_to_m5.py` are **superseded** by `v24_1`, which handles headerless MT5 exports, mixed separators, and skips previously-generated combined files. Use v24.1. (`convert_m1_to_m5.py` also mislabels its input as M1 while reading an M5 filename.)
- `v26` stored absolute minute-of-day in `minutes_after_london`; `v26_1` fixes it to be relative to London open. Any timing conclusion must come from **v26.1 or later**.
- `narrow_asia_v26_output/` is retained only as the record of the buggy pass.
- `eurusd_local_research_v24_2.py` supersedes `v24_1` as the script to *run*, but not as the record: `research_output_v24_1/` was produced by v24.1 and the stable-sort difference means v24.2 does not reproduce it byte-for-byte (same two causes as `rebuild_clean_m5.py`, below). Send v24.2's output to `research_output_v24_2/`.
- `rebuild_clean_m5.py` does **not** reproduce `research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv` byte-for-byte, in two known ways. (1) `tick_volume` is written as `31`, not `31.0` — pandas 3.0.5 keeps the summed column integral where the pandas that built the stored file promoted it to float; running v24.1 itself today shows the same drift, so it is a pandas-version artifact, not a port bug. (2) **12 rows differ**, all at month-boundary midnights. v24.1 sorted with the default non-stable quicksort before `drop_duplicates(keep="last")`, so when a month export's stray trailing bar, the next month's file and the yearly `*_all.csv` all claimed one timestamp, the surviving row was arbitrary — the stored dataset kept 1-to-5-tick fragments there (e.g. `2021-06-01 00:00` has `tick_volume` 1 instead of 19). The extracted loader sorts `kind="stable"`, so "last file wins" is what actually happens. Values are otherwise identical across all 485,160 rows.
- The committed `*_output/` files have **CRLF** line endings; a re-run on Linux writes LF, so a plain `diff` reports every line as changed. Use `diff --strip-trailing-cr` when checking whether a re-run reproduces a stored result. (Verified 2026-08-24: pandas 3.0.5 reproduces all of `behavior_atlas_v25_output/` byte-for-byte modulo line endings.)
- `/data/` and `__pycache__/` are gitignored; the `*_output/` directories are intended to be tracked.
