"""Console display for a `tools.bar_window.BarWindow`.

    from ui.bar_window_view import display_bar_window

    display_bar_window(window, decimals=args.decimals)

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
    """Turn Bars into aligned text columns, dropping columns nothing uses."""
    header = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL"]

    if bar_window.has_real_volume:
        header.append("VOL")

    if bar_window.has_spread:
        header.append("SPREAD")

    rows = []

    for bar in bar_window:
        row = [
            bar.dt.strftime("%Y.%m.%d"),
            bar.dt.strftime("%H:%M"),
            f"{bar.open:.{decimals}f}",
            f"{bar.high:.{decimals}f}",
            f"{bar.low:.{decimals}f}",
            f"{bar.close:.{decimals}f}",
            f"{bar.tick_volume:,}",
        ]

        if bar_window.has_real_volume:
            row.append(f"{bar.real_volume:,}")

        if bar_window.has_spread:
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
