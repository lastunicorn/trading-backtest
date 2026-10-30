"""Print an MT5 export to the console, raw or resampled.

Utility: reads via ports.mt5_file_access and either
displays -- nothing written to disk -- or, with --output, writes the
processed data to a CSV.

    python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv        # first 20 bars
    python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv --tail --rows 5
    python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv --all | less
    python3 read_csv_as_frame.py data/eurusd/1min --interval 5m              # whole folder, resampled to M5
    python3 read_csv_as_frame.py data/eurusd/1min --interval 1w              # resampled to weekly bars
    python3 read_csv_as_frame.py data/eurusd/1min --timezone UTC             # broker-server time -> UTC
    python3 read_csv_as_frame.py data/eurusd/1min --output scratch/jan.csv   # write instead of display
    python3 read_csv_as_frame.py path/to/other.csv --decimals 3
    python3 read_csv_as_frame.py data/eurusd/1min/EURUSD_2020_01.csv --source-symbol EURUSD  # fixed decimals

`source` is a single file or a folder of exports (see ports.file_system_access
.find_files) -- a folder's files are read in name order, which is chronological
for this repo's monthly exports. The pipeline is always: read every file into
one frame, clean it up (sort, drop duplicate timestamps), optionally shift
timezone (--timezone; off by default -- bars display in raw broker-server
time otherwise), optionally resample (--interval), then display or write
(--output). See domain.sample_size.SampleSize for the --interval syntax (5m,
4h, 7d, 2w, 3M, ...); resampling uses plain pandas bucket semantics (see
domain.pandas_approach.frames.resample_ohlc). Price decimals come from
--decimals if given, else --source-symbol's ticker (via domain.symbol
.by_ticker), else default number formatting; --output writes prices with
that same formatting.

--rows/--all/--tail only affect the console display; --output always writes
the full processed frame regardless of them, but with the same
--decimals/--source-symbol formatting applied to its prices.

Requires pandas (see requirements.txt); activate .venv first.
"""

import argparse
import sys
import time

import pandas as pd

from domain.pandas_approach.frames import clean_frame, resample_ohlc
from domain.broker_clock import BROKER_SERVER_TZ, timezone_name
from domain.pandas_approach.shift_timezone import shift_timezone
from domain.sample_size import SampleSize
from domain.symbol import by_ticker
from ports.file_system_access.file_system import find_files
from ports.mt5_file_access import read_frame, write_frame
from ui.cli_args import timezone_arg
from ui.frame_table_view import display_frame


def main():
    start_time = time.perf_counter()
    args = parse_args()

    paths = find_files(args.source, pattern="*.csv")

    if not paths:
        print(f"ERROR: no csv files found at {args.source!r}", file=sys.stderr)
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
        frame = read_all(paths, strict=args.strict, on_skip=on_skip)
    except Exception as exc:  # BarParseError (strict mode) or a bad file
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if frame.empty:
        print(f"ERROR: no bars found at {args.source}", file=sys.stderr)
        return 1

    frame = clean_frame(frame)

    if args.timezone is not None:
        frame = shift_timezone(frame, args.timezone)

    if interval is not None:
        frame = resample_ohlc(frame, interval)

    elapsed_data_processing = time.perf_counter() - start_time

    print("=" * 64)
    print(f"SOURCE: {args.source}" + (f"  ({len(paths)} files)" if len(paths) > 1 else ""))

    if args.interval:
        print(f"RESAMPLE: {args.interval}")

    if args.timezone is not None:
        print(f"TIMEZONE: {timezone_name(args.timezone)}")

    print("=" * 64)
    print(f"Timezone: {BROKER_SERVER_TZ if args.timezone is None else timezone_name(args.timezone)}")
    print(f"Bars:   {len(frame):,}")
    print(f"First:  {frame['datetime'].iloc[0]:%Y.%m.%d %H:%M}")
    print(f"Last:   {frame['datetime'].iloc[-1]:%Y.%m.%d %H:%M}")
    print(f"Span:   {(frame['datetime'].iloc[-1] - frame['datetime'].iloc[0]).days} days")

    if skipped:
        print(f"Skipped: {len(skipped):,} malformed line(s) -- first at line "
              f"{skipped[0][0]}: {skipped[0][1]}")

    if args.output:
        write_frame(frame, args.output, decimals=decimals)
        print(f"\nWritten: {args.output}")
    else:
        display_frame(frame, rows=None if args.all else max(args.rows, 0), tail=args.tail, decimals=decimals)

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
        type=timezone_arg,
        default=None,
        metavar="TZ",
        help="Shift from broker-server time (New York + 7h, see domain.broker_clock) "
             "to this IANA timezone before display, e.g. 'UTC', 'Europe/London' "
             "(omit to keep broker-server time).",
    )

    parser.add_argument(
        "--decimals",
        type=int,
        default=None,
        help="Price decimals for display and --output, overriding "
             "--source-symbol (default: derived from --source-symbol, or "
             "default number formatting if that's also omitted).",
    )

    parser.add_argument(
        "--source-symbol",
        default=None,
        metavar="TICKER",
        help="Symbol whose tick size sets price decimals for display and "
             "--output, e.g. 'EURUSD', 'XAUUSD' (see show_symbol.py for the "
             "full list; omit for default number formatting, unless "
             "--decimals is set).",
    )

    parser.add_argument(
        "--output",
        default=None,
        metavar="PATH",
        help="Write the processed data to this CSV instead of displaying it "
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
        "--strict",
        action="store_true",
        help="Abort on a malformed line instead of skipping it.",
    )

    return parser.parse_args()


def read_all(paths, *, strict, on_skip):
    """Read every file at `paths` into one frame, in file order.

    No sorting, no dedup -- just concatenation; `clean_frame` is the next
    pipeline step, deliberately separate.
    """
    pieces = [read_frame(path, strict=strict, on_skip=on_skip) for path in paths]
    return pd.concat(pieces, ignore_index=True)


if __name__ == "__main__":
    sys.exit(main())
