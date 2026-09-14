"""Print an MT5 export to the console, raw or resampled.

Utility, not a research stage: reads via ports.mt5_file_access and displays --
nothing written to disk. Use it to eyeball what an export actually contains
before feeding it to eurusd_local_research_v24_1.py, or to sanity-check a
resample interval.

    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv        # first 20 bars
    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
    python3 show_csv.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
    python3 show_csv.py data/eurusd/1min --interval 5m              # whole folder, resampled to M5
    python3 show_csv.py data/eurusd/1min --interval 1w              # resampled to weekly bars
    python3 show_csv.py path/to/other.csv --decimals 3

`source` is a single file or a folder of exports (see ports.file_system_access
.find_files) -- a folder's files are read in name order, which is chronological
for this repo's monthly exports. `--interval` resamples via
domain.resample_bars before display; omit it to show bars as read. See that
module's docstring for the interval syntax (5m, 4h, 7d, 2w, 3M, ...) and what
each unit anchors to.

Stdlib only (pandas is not used).
"""

import argparse
import sys
from zoneinfo import ZoneInfo

from domain.resample_bars import resample_bars
from domain.sample_interval import SampleInterval
from domain.shift_bars import shift_bars
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import BarParseError, iterate_bars
from ui.bar_window import BarWindow
from ui.bar_window_view import display_bar_window


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
        default=None,
        help="Resample before display, e.g. '5m', '4h', '7d', '2w', '3M' "
             "(m/h/d/w/M, case-sensitive; omit to show raw bars).",
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
        yield from iterate_bars(str(path), strict=False, on_skip=on_skip)


def main():
    args = parse_args()

    paths = find_files(args.source)

    if not paths:
        print(f"ERROR: no csv files found at {args.source!r}", file=sys.stderr)
        return 1

    interval = None

    if args.interval:
        try:
            interval = SampleInterval.Parse(args.interval)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    skipped = []

    def on_skip(line_no, line, reason):
        skipped.append((line_no, reason))

    bars = read_bars(paths, on_skip)
    # Broker server time is US Eastern; ZoneInfo applies the correct
    # EST/EDT offset per bar instead of a fixed hour count.
    bars = shift_bars(bars, ZoneInfo("America/New_York"))

    if interval:
        bars = resample_bars(bars, interval)

    count = None if args.all else max(args.rows, 0)
    window = BarWindow(bars, count=count, tail=args.tail)

    try:
        window.read_all()
    except BarParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: could not read {args.source}: {exc}", file=sys.stderr)
        return 1

    if window.total_count == 0:
        print(f"ERROR: no bars found at {args.source}", file=sys.stderr)
        return 1

    if args.strict and skipped:
        line_no, reason = skipped[0]
        print(f"ERROR: {args.source}: line {line_no}: {reason}", file=sys.stderr)
        return 1

    print("=" * 64)
    print(f"SOURCE: {args.source}" + (f"  ({len(paths)} files)" if len(paths) > 1 else ""))

    if args.interval:
        print(f"RESAMPLE: {args.interval}")

    print("=" * 64)
    print(f"Bars:   {window.total_count:,}")
    print(f"First:  {window.first_bar.dt:%Y.%m.%d %H:%M}")
    print(f"Last:   {window.last_bar.dt:%Y.%m.%d %H:%M}")
    print(f"Span:   {(window.last_bar.dt - window.first_bar.dt).days} days")

    if skipped:
        print(f"Skipped: {len(skipped):,} malformed line(s) -- first at line "
              f"{skipped[0][0]}: {skipped[0][1]}")

    display_bar_window(window, decimals=args.decimals)

    return 0


if __name__ == "__main__":
    sys.exit(main())
