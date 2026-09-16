"""Display every `Symbol` defined in domain.symbol, or just the ones matching
a ticker/name filter.

Utility, not a research stage -- reads nothing from disk, just prints the
fixed pip/tick specifications domain.symbol defines.

    python3 show_symbol.py                # every symbol
    python3 show_symbol.py --filter jpy    # ticker or name contains "jpy" (case-insensitive)
    python3 show_symbol.py --filter dollar

New `Symbol` subclasses in domain.symbol are picked up automatically -- this
walks `Symbol.__subclasses__()` rather than keeping its own list, so there's
nothing to update here when a symbol is added there.

Stdlib only.
"""

import argparse
import sys

from domain.symbol import Symbol
from ui.bar_window_view import format_table


def main():
    args = parse_args()

    symbols = get_all_symbols()

    if args.filter:
        symbols = [symbol for symbol in symbols if matches(symbol, args.filter)]

    if not symbols:
        print(f"ERROR: no symbol matches {args.filter!r}", file=sys.stderr)
        return 1

    header, rows = build_rows(symbols)

    for line in format_table(header, rows, left_align={1}):  # NAME
        print(line)

    return 0


def parse_args():
    parser = argparse.ArgumentParser(
        description="Display the Symbol specifications defined in domain.symbol."
    )

    parser.add_argument(
        "--filter",
        default=None,
        help="Only show symbols whose ticker or name contains this text (case-insensitive).",
    )

    return parser.parse_args()


def get_all_symbols():
    """Every concrete `Symbol` subclass in domain.symbol, instantiated and
    sorted by ticker."""
    return sorted((cls() for cls in Symbol.__subclasses__()), key=lambda symbol: symbol.ticker)


def matches(symbol, text):
    text = text.lower()
    return text in symbol.ticker.lower() or text in symbol.name.lower()


def build_rows(symbols):
    header = ["TICKER", "NAME", "PIP SIZE", "TICK SIZE", "DECIMALS"]

    rows = [
        [
            symbol.ticker,
            symbol.name,
            f"{symbol.pip_size:.{symbol.price_decimals}f}",
            f"{symbol.tick_size:.{symbol.price_decimals}f}",
            str(symbol.price_decimals),
        ]
        for symbol in symbols
    ]

    return header, rows


if __name__ == "__main__":
    sys.exit(main())
