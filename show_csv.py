"""Print an MT5 export to the console, raw or resampled.

Utility, not a research stage: reads via ports.mt5_file_access and displays --
nothing written to disk. Use it to eyeball what an export actually contains
before feeding it to eurusd_local_research_v24_1.py, or to sanity-check a
resample interval.

    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv        # first 20 bars
    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
    python3 show_csv.py data/eurusd/1min --interval 5               # whole folder, resampled to M5
    python3 show_csv.py path/to/other.csv --decimals 3

`source` is a single file or a folder of exports (see ports.file_system_access
.find_files) -- a folder's files are read in name order, which is chronological
for this repo's monthly exports. `--interval` resamples via
tools.resample_bars before display; 0 (the default) shows bars as read.

Stdlib only (pandas is not used).
"""

import argparse
import sys
from collections import deque

from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import BarParseError, iter_bars
from tools.resample_bars import resample_bars


def parse_args():
    parser = argparse.ArgumentParser(
        description="Display an MT5 CSV export in the console, raw or resampled."
    )

    parser.add_argument(
        "source",
        help="CSV file, or a folder of exports, to display.",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=0,
        help="Resample to N-minute bars before display (default: 0, meaning raw bars).",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=20,
        help="How many bars to show (default: 20). Ignored with --all.",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Show every bar instead of just --rows.",
    )

    parser.add_argument(
        "--tail",
        action="store_true",
        help="Show the last bars instead of the first.",
    )

    parser.add_argument(
        "--decimals",
        type=int,
        default=5,
        help="Price decimals (default: 5, correct for EURUSD).",
    )

    parser.add_argument(
        "--strict",
        action="store_true",
        help="Abort on a malformed line instead of skipping it.",
    )

    return parser.parse_args()


def read_bars(paths, on_skip):
    for path in paths:
        yield from iter_bars(str(path), strict=False, on_skip=on_skip)


def scan(paths, *, interval_minutes, want, tail, show_all, on_skip):
    """One streaming pass: collect the bars to display, count the rest.

    Keeps only what gets printed, so a 2.5M-row file costs no more memory than
    a 31k-row one (unless --all was asked for). `interval_minutes` > 0 resamples
    the stream before it's counted or selected from.
    """
    bars = read_bars(paths, on_skip)

    if interval_minutes:
        bars = resample_bars(bars, interval_minutes)

    selected = [] if not tail else deque(maxlen=want)
    total = 0
    first = None
    last = None

    for bar in bars:
        total += 1

        if first is None:
            first = bar

        last = bar

        if tail:
            selected.append(bar)
        elif show_all or len(selected) < want:
            selected.append(bar)

    return list(selected), total, first, last


def build_rows(bars, decimals):
    """Turn Bars into aligned text columns, dropping columns nothing uses."""
    show_spread = any(bar.spread is not None for bar in bars)
    show_real_volume = any(bar.real_volume for bar in bars)

    header = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL"]

    if show_real_volume:
        header.append("VOL")

    if show_spread:
        header.append("SPREAD")

    rows = []

    for bar in bars:
        row = [
            bar.dt.strftime("%Y.%m.%d"),
            bar.dt.strftime("%H:%M"),
            f"{bar.open:.{decimals}f}",
            f"{bar.high:.{decimals}f}",
            f"{bar.low:.{decimals}f}",
            f"{bar.close:.{decimals}f}",
            f"{bar.tick_volume:,}",
        ]

        if show_real_volume:
            row.append(f"{bar.real_volume:,}")

        if show_spread:
            row.append("" if bar.spread is None else str(bar.spread))

        rows.append(row)

    return header, rows


def format_table(header, rows):
    widths = [len(name) for name in header]

    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    lines = ["  ".join(name.rjust(widths[i]) for i, name in enumerate(header))]
    lines.append("  ".join("-" * width for width in widths))

    for row in rows:
        lines.append("  ".join(cell.rjust(widths[i]) for i, cell in enumerate(row)))

    return lines


def main():
    args = parse_args()

    paths = find_files(args.source)

    if not paths:
        print(f"ERROR: no csv files found at {args.source!r}", file=sys.stderr)
        return 1

    if args.interval < 0:
        print(f"ERROR: --interval must not be negative, got {args.interval}", file=sys.stderr)
        return 1

    skipped = []

    def on_skip(line_no, line, reason):
        skipped.append((line_no, reason))

    try:
        bars, total, first, last = scan(
            paths,
            interval_minutes=args.interval,
            want=max(args.rows, 0),
            tail=args.tail,
            show_all=args.all,
            on_skip=on_skip,
        )
    except BarParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: could not read {args.source}: {exc}", file=sys.stderr)
        return 1

    if total == 0:
        print(f"ERROR: no bars found at {args.source}", file=sys.stderr)
        return 1

    if args.strict and skipped:
        line_no, reason = skipped[0]
        print(f"ERROR: {args.source}: line {line_no}: {reason}", file=sys.stderr)
        return 1

    span = last.dt - first.dt

    print("=" * 64)
    print(f"SOURCE: {args.source}" + (f"  ({len(paths)} files)" if len(paths) > 1 else ""))

    if args.interval:
        print(f"RESAMPLE: {args.interval}-minute bars")

    print("=" * 64)
    print(f"Bars:   {total:,}")
    print(f"First:  {first.dt:%Y.%m.%d %H:%M}")
    print(f"Last:   {last.dt:%Y.%m.%d %H:%M}")
    print(f"Span:   {span.days} days")

    if skipped:
        print(f"Skipped: {len(skipped):,} malformed line(s) -- first at line "
              f"{skipped[0][0]}: {skipped[0][1]}")

    if args.all:
        label = "all bars"
    elif args.tail:
        label = f"last {len(bars)} bars"
    else:
        label = f"first {len(bars)} bars"

    print("")
    print(f"--- {label} ---")

    header, rows = build_rows(bars, args.decimals)

    for line in format_table(header, rows):
        print(line)

    if len(bars) < total:
        print(f"... {total - len(bars):,} more bars (use --all, or --rows N)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
