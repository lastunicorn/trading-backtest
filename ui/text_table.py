"""Plain-text tables for the console: aligned columns under a dashed rule.

    from ui.text_table import format_table

    for line in format_table(["TICKER", "NAME"], [["EURUSD", "Euro / U.S. Dollar"]], left_align={1}):
        print(line)

Knows nothing about bars or frames -- callers turn their data into rows of
strings first (`frame_table_view`, `show_symbol.py`).
"""


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
