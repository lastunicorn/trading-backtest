# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

A quantitative research log for **one** EURUSD intraday strategy ("Candle DNA — Narrow Asia London Fade"), not an application. Each `eurusd_*_vNN.py` file is a self-contained, immutable research stage: a numbered snapshot of what was known at that point. Later versions supersede earlier ones but the earlier ones are kept for provenance.

**Do not edit a completed vNN script to change its findings.** New analysis goes in a new version file (the established convention: `v26` → `v26_1` for a bugfix pass, `v27` → `v28` for a new question). The `output/` directory (gitignored, local-only) holds the archived run of each stage — treat it as the provenance record: regenerating a run overwrites what a script produced, so only do it deliberately.

## Reviewing requests

Before implementing a request as literally stated, check it against good practice, and say so if a better approach exists rather than silently building the literal ask. "Good" means:

- Easy for a human to read, easy to maintain long-term, easy to debug and extend.
- Leaves a seam where a future need is genuinely likely — a parameter, a hook, a clear boundary — without building the extension itself. A small amount of extra effort here is worth it; building the unrequested feature is not.

## Pipeline (strictly sequential)

```
data/eurusd/1min/EURUSD_YYYY_MM.csv     raw MT5 M1 exports, 78 monthly files 2020-01..2026-06 (gitignored)
  └─ eurusd_local_research_v24_1.py     robust MT5 loader → M1→M5 → dedupe → data-quality report
     eurusd_local_research_v24_2.py     same study on the shared ports/ + domain/ + application/ loader
       └─ output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv   ← the canonical dataset
            ├─ eurusd_behavior_atlas_v25.py       behavior discovery (no optimization)
            ├─ eurusd_narrow_asia_reversion_v26.py / _v26_1.py  trajectory analysis
            ├─ eurusd_narrow_asia_fade_v27.py     trade simulation / expectancy grid
            └─ eurusd_narrow_asia_torture_v28.py  robustness of the frozen v27 strategy
```

Everything from v25 onward takes the clean M5 CSV as its single positional argument.

### Commands

```bash
# Stage 0 — rebuild the clean M5 dataset from raw MT5 exports (only if raw data changed)
python3 eurusd_local_research_v24_2.py --folder data/eurusd/1min --out output/research_output_v24_2
python3 eurusd_local_research_v24_2.py --clean-csv output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv

# Stages 1-4 — each writes CSVs + a <version>_report.txt into its own --out dir
python3 eurusd_behavior_atlas_v25.py          output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_reversion_v26_1.py output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_fade_v27.py        output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
python3 eurusd_narrow_asia_torture_v28.py     output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv
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

The v25–v28 scripts take session-window flags in **broker server time**, not UTC or exchange time: `--asia-start`, `--asia-end`, `--london-open` on all four; `--study-end` on v26_1/v27/v28; `--ny-open` and `--day-end` on v25. Defaults: Asia 02:00–10:00, London open 10:00, study end 14:00, NY open 15:30.

## Tooling outside the pipeline

`ports/`, `domain/`, `application/`, `tools/`, `show_csv.py` and `resample_csv.py` are **not** research stages. They are shared code: reading raw data, and building the clean dataset the pipeline consumes. They are versionless and freely editable — the immutability rule applies only to `eurusd_*_vNN.py`.

The split between the packages is the point of the layout:

- **`ports/`** knows *file formats*. A port parses records and stops — no cleaning, no deduplication, no resampling, whether it hands back `Bar` objects or a DataFrame. Most ports are **stdlib-only** (no pandas, no numpy), so they run in any sandbox as-is; `mt5_file_access.mt5_frame_reader` is the deliberate exception, using pandas to build the DataFrame directly. `Bar` itself is a `domain/` entity (`domain/bar.py`) — the MT5 port parses files into it but does not own it.
- **`domain/`** knows *what the data means*: what one OHLC candle is (`bar.Bar`), how bars collapse into a coarser timeframe (`frames.resample_ohlc`), which of two rows claiming the same timestamp wins. `domain/frames.py` is where pandas lives; `domain/bar.py` is stdlib-only, which is what lets `ports/` depend on it. `domain/` never reads or writes files, and never imports `ports/` or `application/`.
- **`application/`** wires `ports/` and `domain/` into a whole task: read the raw exports, resample and merge, write the result, return the numbers a CLI prints. The I/O that `domain/` refuses lives here.

```
ports/mt5_file_access/mt5_bar_reader.py   MT5 CSV → `Bar` objects (dt, OHLC, volumes, spread)            [stdlib]
ports/mt5_file_access/mt5_frame_reader.py MT5 CSV → pandas frame directly, same fields                  [pandas]
ports/file_system_access/file_system.py   list the source csv files in a folder (or pass one file through) [stdlib]
domain/bar.py                             the `Bar` entity — one OHLC candle (dt, OHLC, volumes, spread)  [stdlib]
domain/frames.py                          resample a frame to a coarser timeframe                        [pandas]
application/build_clean_dataset_use_case.py  folder of exports → one clean, deduplicated frame (in memory)
tools/resample_bars.py                    resample an iterable of `Bar` to a coarser grid, streaming    [stdlib]
show_csv.py                               CLI that prints an export as an aligned table, raw or resampled
resample_csv.py                           folder/file of M1 exports → merged CSV on a coarser grid + report — stage 0 straight to a file
```

```python
from ports.mt5_file_access import read_bars, iter_bars   # short form (re-exported)

bars = read_bars(path)      # list[Bar] — fine for one monthly export (~31k bars)
for bar in iter_bars(path): # generator — constant memory; use on multi-million-row files
    ...
```

The reader detects the separator (comma/tab/semicolon) and handles both headerless exports and `<DATE>`-style MT5 headers. `strict=True` (default) raises `BarParseError` on a malformed line; `strict=False` skips it and reports via an `on_skip` callback. `detect_layout(path)` reports which fields an export carries without parsing it.

Everything after parsing is `domain/` (concepts) and `application/` (use cases) — the loading half of `eurusd_local_research_v24_1.py`, extracted so tooling and future stages stop re-implementing it:

```python
from ports.mt5_file_access import read_frame
from domain.frames import resample_ohlc
from application.build_clean_dataset_use_case import build_clean_dataset

m5 = resample_ohlc(read_frame("data/eurusd/1min/EURUSD_2020_01.csv"), "M5")

dataset = build_clean_dataset("data/eurusd/1min", progress=print)  # every export in the folder
dataset.frame, dataset.stats, dataset.errors, dataset.duplicates_removed_count
dataset.timeframe                # "M5" — a report never has to be told the timeframe
```

`build_clean_dataset` returns data and never prints or writes — reporting belongs to the caller. For the pipeline, `eurusd_local_research_v24_2.py` is that caller: its `build_clean_m5()` writes the clean CSV plus `v24_2_data_quality.txt` into `--out`. v24.1 keeps its own private copy of the loader and is still the script of record for what produced `output/research_output_v24_1/`.

`eurusd_local_research_v24_2.py` is the research-stage counterpart: the *same* v24.1 study — stage-0 build plus the range/delay/stop/reward grid — with the private loader deleted in favour of `build_clean_dataset()`. Its grid half is carried over unchanged and reproduces v24.1's `range_grid.csv` and `session_report.txt` byte-for-byte on identical input (verified on a two-month subset). What it adds: unparsable source lines are counted in the quality report instead of vanishing, sorting is stable (see the stable-sort gotcha below), `--out` is a free-standing path rather than a fixed directory inside `--folder`, and `--clean-csv` skips the rebuild to study an existing clean M5 file. Prefer v24.2 for new stage-0 runs; v24.1 stays untouched as the provenance of `output/research_output_v24_1/`.

`resample_csv.py` runs the same stage-0 build through its own `resample()` function instead of `build_clean_dataset()`, and — unlike `build_clean_dataset` — does the writing itself. (`resample()` used to live in a separate `application/resample_use_case.py` module; since this script was its only caller, that logic now lives directly in `resample_csv.py`.) It emits two files: the clean CSV and a report beside it named for the CSV (`output_M5.csv` → `output_M5.report.txt`), overwriting an existing file after printing an `INFO:` line. `--source`, `--destination` and `--timeframe` are all required (no defaults). `--source` is a folder of raw M1 exports or a single csv file — the source data must always be M1; `--destination` is a file path, or a directory, in which case it writes `output_<timeframe>.csv` inside it:

```bash
python3 resample_csv.py --source data/eurusd/1min --destination data/eurusd/5min/EURUSD.csv --timeframe M5
python3 resample_csv.py --source data/eurusd/1min --destination data/eurusd/15min/EURUSD.csv --timeframe M15
python3 resample_csv.py --source data/eurusd/1min/EURUSD_2020_01.csv --destination scratch/jan.csv --timeframe M5
```

`show_csv.py`'s `source` is a single file or a folder of exports (`ports.file_system_access.find_files` — a folder is read file-by-file in name order, chronological for this repo's monthly exports). It runs a pandas pipeline: read every file into one frame, clean it up (stable sort + drop duplicate timestamps, `domain.pandas_approach.frames.clean_frame`), optionally shift timezone (`--timezone`, off by default — bars display in raw broker-server time otherwise), optionally resample (`--interval`, via `domain.pandas_approach.frames.resample_ohlc` with plain pandas bucket semantics — see `domain.sample_size.SampleSize` for the `5m`/`4h`/`7d`/`2w`/`3M` syntax), then display or write (`--output`, which always writes the full processed frame regardless of `--rows`/`--all`/`--tail`):

```bash
python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv            # first 20 bars (the source arg is required)
python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
python3 show_csv.py path/to/export.csv --decimals 3
python3 show_csv.py data/eurusd/1min --interval 5m                 # whole folder, resampled to M5
python3 show_csv.py data/eurusd/1min --timezone UTC                # broker-server time -> UTC
python3 show_csv.py data/eurusd/1min --interval 5m --output scratch/jan_m5.csv  # write instead of display
```

`ports/`, `ports/mt5_file_access/`, `ports/file_system_access/`, `domain/` and `application/` are regular packages (each has an `__init__.py`), and the CLIs must stay at the repo root for `ports.*` / `domain.*` / `application.*` to resolve from any working directory.

## Testing

Unit tests live under `tests/`, mirroring the source package layout (`tests/domain/...`, `tests/application/...`). `pytest.ini` sets `testpaths = tests`; run everything with `pytest` from the repo root (inside the activated venv).

For a class or module under test, create a directory named after the file being tested, and inside it one test file per function/method tested (e.g. `domain/trading_session_template.py`'s `TradingSessionTemplate.start_time_on` is tested in `tests/domain/trading_session_template/test_start_time_on.py`). This holds even for small, single-line delegating methods — keep each function's tests isolated rather than folding several into one file. Give every package directory (including `tests/` itself and each subpackage) an `__init__.py`.

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

- `eurusd_local_research_v24.py` and the ad-hoc `combine_csv.py` are **superseded** by `v24_1` (and, for stage 0, `v24_2`), which handles headerless MT5 exports, mixed separators, and skips previously-generated combined files. `convert_m1_to_m5.py`, another early converter, was deleted once the `ports/` + `domain/` loader replaced it.
- `v26` stored absolute minute-of-day in `minutes_after_london`; `v26_1` fixes it to be relative to London open. Any timing conclusion must come from **v26.1 or later**.
- `output/narrow_asia_v26_output/` is retained only as the record of the buggy pass.
- `eurusd_local_research_v24_2.py` supersedes `v24_1` as the script to *run*, but not as the record: `output/research_output_v24_1/` was produced by v24.1 and the stable-sort difference means v24.2 does not reproduce it byte-for-byte (same two causes as the next bullet). Send v24.2's output to `output/research_output_v24_2/`.
- The shared loader (`eurusd_local_research_v24_2.py`, `resample_csv.py`) does **not** reproduce `output/research_output_v24_1/EURUSD_M5_CLEAN_2020_2026.csv` byte-for-byte, in two known ways. (1) `tick_volume` is written as `31`, not `31.0` — pandas 3.0.5 keeps the summed column integral where the pandas that built the stored file promoted it to float; running v24.1 itself today shows the same drift, so it is a pandas-version artifact, not a port bug. (2) **12 rows differ**, all at month-boundary midnights. v24.1 sorted with the default non-stable quicksort before `drop_duplicates(keep="last")`, so when a month export's stray trailing bar, the next month's file and a yearly `*_all.csv` (present in the 84-file set that built the stored dataset) all claimed one timestamp, the surviving row was arbitrary — the stored dataset kept 1-to-5-tick fragments there (e.g. `2021-06-01 00:00` has `tick_volume` 1 instead of 19). The extracted loader sorts `kind="stable"`, so "last file wins" is what actually happens. Values are otherwise identical across all 485,160 rows.
- The archived `output/**` files have **CRLF** line endings; a re-run on Linux writes LF, so a plain `diff` reports every line as changed. Use `diff --strip-trailing-cr` when checking whether a re-run reproduces a stored result. (Verified 2026-08-24: pandas 3.0.5 reproduces all of `output/behavior_atlas_v25_output/` byte-for-byte modulo line endings.)
- `.gitignore` covers `/data/`, `/output/`, `/*_output/`, `.venv/` and `__pycache__/`: the raw exports, every run directory, and the venv are all local-only. Nothing under `output/` is version-controlled — it is a manual archive.
- `read_csv_as_frame.py --output` is **not** a substitute for `resample_csv.py`, even though both can write a resampled CSV. `resample_csv.py` resamples each source file individually and dedups the *resampled* rows across files afterward, matching the pipeline's stage-0 convention and its month-boundary tie-break; it's also the only one of the two that writes a `.report.txt` provenance record and that survives a single bad source file (per-file errors are logged, not fatal). `read_csv_as_frame.py` concatenates every raw file first, dedups the *raw M1* rows once, then resamples the whole thing — a different tie-break at month boundaries, no report, and one bad file aborts the run. Use `resample_csv.py` for anything that feeds the pipeline; `read_csv_as_frame.py` is for ad hoc inspection.
