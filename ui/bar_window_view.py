"""Console display for a `ui.bar_window.BarWindow`.

    from ui.bar_window_view import display_bar_window

    display_bar_window(window, decimals=args.decimals)
    display_bar_window(window, decimals=None)  # default number formatting

`window` must already be fully read (via `window.read_all()`) and have at
least one bar -- this module only prints the bar table, it doesn't validate
and knows nothing about where the bars came from (that's the caller's job).
"""


def display_bar_window(window, *, decimals):
    """Print the bar table's label, its rows, and any truncation note."""
    if window.is_all_visible:
        label = "all bars"
    elif window.tail:
        label = f"last {window.total_visible_count} bars"
    else:
        label = f"first {window.total_visible_count} bars"

    print("")
    print(f"--- {label} ---")

    header, rows = build_rows(window, decimals)

    for line in format_table(header, rows):
        print(line)

    if window.total_visible_count < window.total_count:
        print(f"... {window.total_count - window.total_visible_count:,} more bars (use --all, or --rows N)")


def build_rows(bar_window, decimals):
    """Turn Bars into aligned text columns, dropping columns nothing uses.

    `decimals=None` means no symbol was given to format against -- prices
    fall back to plain `str()` rather than a fixed decimal count.
    """
    header = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL"]

    if bar_window.has_real_volume:
        header.append("VOL")

    if bar_window.has_spread:
        header.append("SPREAD")

    format_price = (lambda value: str(value)) if decimals is None else (lambda value: f"{value:.{decimals}f}")

    rows = []

    for bar in bar_window:
        row = [
            bar.dt.strftime("%Y.%m.%d"),
            bar.dt.strftime("%H:%M"),
            format_price(bar.open),
            format_price(bar.high),
            format_price(bar.low),
            format_price(bar.close),
            f"{bar.tick_volume:,}",
        ]

        if bar_window.has_real_volume:
            row.append(f"{bar.real_volume:,}")

        if bar_window.has_spread:
            row.append("" if bar.spread is None else str(bar.spread))

        rows.append(row)

    return header, rows


def format_table(header, rows, left_align=frozenset()):
    """Align each column to `widths`, right-justified except for column
    indices named in `left_align` (e.g. free-text columns like a name or
    label, where right-justifying just reads oddly)."""
    widths = [len(name) for name in header]

    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def justify(cell, i):
        return cell.ljust(widths[i]) if i in left_align else cell.rjust(widths[i])

    lines = ["  ".join(justify(name, i) for i, name in enumerate(header))]
    lines.append("  ".join("-" * width for width in widths))

    for row in rows:
        lines.append("  ".join(justify(cell, i) for i, cell in enumerate(row)))

    return lines
