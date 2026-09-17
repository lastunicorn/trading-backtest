"""Print an MT5 export to the console, raw or resampled.

Utility, not a research stage: reads via ports.mt5_file_access and either
displays -- nothing written to disk -- or, with --output, writes the
processed bars to a CSV.

    python3 read_csv_as_bars.py data/eurusd/1min/EURUSD_2020_01.csv        # first 20 bars
    python3 read_csv_as_bars.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
    python3 read_csv_as_bars.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
    python3 read_csv_as_bars.py data/eurusd/1min --interval 5m              # whole folder, resampled to M5
    python3 read_csv_as_bars.py data/eurusd/1min --interval 1w              # resampled to weekly bars
    python3 read_csv_as_bars.py data/eurusd/1min --timezone UTC             # broker-server time -> UTC
    python3 read_csv_as_bars.py data/eurusd/1min --output scratch/jan.csv   # write instead of display
    python3 read_csv_as_bars.py path/to/other.csv --decimals 3
    python3 read_csv_as_bars.py path/to/other.csv --source-symbol EURUSD

`source` is a single file or a folder of exports (see ports.file_system_access
.find_files) -- a folder's files are read in name order, which is chronological
for this repo's monthly exports. The pipeline is always: read every file into
one bar list, clean it up (sort, drop duplicate timestamps), optionally shift
timezone (--timezone; off by default -- bars display in raw broker-server
time otherwise), optionally resample (--interval, via domain.resample_bars --
see that module's docstring for the interval syntax and what each unit
anchors to), then display or write (--output). Price decimals come from
--decimals if given, else --source-symbol's ticker (via domain.symbol
.by_ticker), else default number formatting.

--rows/--all/--tail/--decimals/--source-symbol only affect the console
display; --output always writes the full processed bar list regardless of
them.

Stdlib only (pandas is not used).
"""

import argparse
import sys
import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from domain.bar_approach.clean_bars import clean_bars
from domain.bar_approach.resample_bars import resample_bars
from domain.sample_size import SampleSize
from domain.bar_approach.shift_bars import shift_bars
from domain.symbol import by_ticker
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import BarParseError, iterate_bars, write_bars
from ui.bar_window import BarWindow
from ui.bar_window_view import display_bar_window

_BROKER_SERVER_TZ = ZoneInfo("America/New_York")


def main():
    start_time = time.perf_counter()
    args = parse_args()

    paths = find_files(args.source, pattern="*.csv")

    if not paths:
        print(f"ERROR: no csv files found at {args.source!r}", file=sys.stderr)
        return 1

    target_tz = None

    if args.timezone:
        try:
            target_tz = ZoneInfo(args.timezone)
        except ZoneInfoNotFoundError:
            print(f"ERROR: unknown timezone {args.timezone!r}", file=sys.stderr)
            return 1

    interval = None

    if args.interval:
        try:
            interval = SampleSize.Parse(args.interval)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    decimals = args.decimals

    if decimals is None and args.source_symbol:
        try:
            decimals = by_ticker(args.source_symbol).price_decimals
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    skipped = []

    def on_skip(line_no, line, reason):
        skipped.append((line_no, reason))

    try:
        bars = clean_bars(read_bars(paths, on_skip))
    except BarParseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: could not read {args.source}: {exc}", file=sys.stderr)
        return 1

    if not bars:
        print(f"ERROR: no bars found at {args.source}", file=sys.stderr)
        return 1

    if args.strict and skipped:
        line_no, reason = skipped[0]
        print(f"ERROR: {args.source}: line {line_no}: {reason}", file=sys.stderr)
        return 1

    if target_tz is not None:
        bars = list(shift_bars(bars, _BROKER_SERVER_TZ, target_tz))

    if interval is not None:
        bars = list(resample_bars(bars, interval))

    elapsed_data_processing = time.perf_counter() - start_time

    print("=" * 64)
    print(f"SOURCE: {args.source}" + (f"  ({len(paths)} files)" if len(paths) > 1 else ""))

    if args.interval:
        print(f"RESAMPLE: {args.interval}")

    if args.timezone:
        print(f"TIMEZONE: {args.timezone}")

    print("=" * 64)
    print(f"Timezone: {args.timezone or 'America/New_York (broker-server)'}")
    print(f"Bars:   {len(bars):,}")
    print(f"First:  {bars[0].dt:%Y.%m.%d %H:%M}")
    print(f"Last:   {bars[-1].dt:%Y.%m.%d %H:%M}")
    print(f"Span:   {(bars[-1].dt - bars[0].dt).days} days")

    if skipped:
        print(f"Skipped: {len(skipped):,} malformed line(s) -- first at line "
              f"{skipped[0][0]}: {skipped[0][1]}")

    if args.output:
        write_bars(bars, args.output)
        print(f"\nWritten: {args.output}")
    else:
        count = None if args.all else max(args.rows, 0)
        # BarWindow assumes a single-pass stream (it resumes iteration in
        # read_all() where _select_head/_select_tail left off) -- `bars` is
        # now a materialized list, so hand it a fresh iterator over it rather
        # than the list itself, or read_all() would rescan from the start.
        window = BarWindow(iter(bars), count=count, tail=args.tail)
        window.read_all()
        display_bar_window(window, decimals=decimals)

    elapsed = time.perf_counter() - start_time
    print()
    print(f"Data processing time: {elapsed_data_processing:.2f}s")
    print(f"Total execution time: {elapsed:.2f}s")
    return 0


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
        "--timezone",
        default=None,
        metavar="TZ",
        help="Shift from broker-server time (America/New_York) to this IANA "
             "timezone before display, e.g. 'UTC', 'Europe/London' "
             "(omit to keep broker-server time).",
    )

    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write the processed bars to this CSV instead of displaying them "
             "(ignores --rows/--all/--tail; always writes the full result).",
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
        default=None,
        help="Price decimals, overriding --source-symbol (default: derived "
             "from --source-symbol, or default number formatting if that's "
             "also omitted).",
    )

    parser.add_argument(
        "--source-symbol",
        default=None,
        metavar="TICKER",
        help="Symbol whose tick size sets price decimals for display, e.g. "
             "'EURUSD', 'XAUUSD' (see show_symbol.py for the full list; "
             "omit for default number formatting, unless --decimals is set).",
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


if __name__ == "__main__":
    sys.exit(main())
