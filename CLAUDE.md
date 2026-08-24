# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A quantitative research log for **one** EURUSD intraday strategy ("Candle DNA — Narrow Asia London Fade"), not an application. Each `eurusd_*_vNN.py` file is a self-contained, immutable research stage: a numbered snapshot of what was known at that point. Later versions supersede earlier ones but the earlier ones are kept for provenance.

**Do not edit a completed vNN script to change its findings.** New analysis goes in a new version file (the established convention: `v26` → `v26_1` for a bugfix pass, `v27` → `v28` for a new question). The committed `*_output/` directories are the record of what each script produced; regenerating them changes history, so only do it deliberately.

## Pipeline (strictly sequential)

```
data/eurusd/1min/EURUSD_YYYY_MM.csv     raw MT5 M1 exports, 84 monthly files (gitignored)
  └─ eurusd_local_research_v24_1.py     robust MT5 loader → M1→M5 → dedupe → data-quality report
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
python3 eurusd_local_research_v24_1.py --folder data/eurusd/1min

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

`ports/` and `show_m1_csv.py` are **not** research stages. They are shared, **stdlib-only** helpers (no pandas, no numpy) for inspecting raw data, so they run in this sandbox as-is. They are versionless and freely editable — the immutability rule applies only to `eurusd_*_vNN.py`.

```
ports/data_file_import/bar.py   MT5 CSV → typed `Bar` objects (dt, OHLC, volumes, spread)
show_m1_csv.py                  CLI that prints an export as an aligned table
```

```python
from ports.data_file_import import read_bars, iter_bars   # short form (re-exported)

bars = read_bars(path)      # list[Bar] — fine for one monthly export (~31k bars)
for bar in iter_bars(path): # generator — constant memory; use on multi-million-row files
    ...
```

The reader detects the separator (comma/tab/semicolon) and handles both headerless exports and `<DATE>`-style MT5 headers. `strict=True` (default) raises `BarParseError` on a malformed line; `strict=False` skips it and reports via an `on_skip` callback. It does **no** cleaning, deduping or resampling — that remains `eurusd_local_research_v24_1.py`'s job.

```bash
python3 show_m1_csv.py                       # first 20 bars of data/eurusd/1min/EURUSD_2020_01.csv
python3 show_m1_csv.py --tail --rows 5
python3 show_m1_csv.py --all | less
python3 show_m1_csv.py path/to/export.csv --decimals 3
```

`ports/` is a regular package (both levels have `__init__.py`), and `show_m1_csv.py` must stay at the repo root for the `ports.*` import to resolve from any working directory.

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
- The committed `*_output/` files have **CRLF** line endings; a re-run on Linux writes LF, so a plain `diff` reports every line as changed. Use `diff --strip-trailing-cr` when checking whether a re-run reproduces a stored result. (Verified 2026-08-24: pandas 3.0.5 reproduces all of `behavior_atlas_v25_output/` byte-for-byte modulo line endings.)
- `/data/` and `__pycache__/` are gitignored; the `*_output/` directories are intended to be tracked.
