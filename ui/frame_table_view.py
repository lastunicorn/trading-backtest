"""Console display for a bar DataFrame (`domain.pandas_approach`).

    from ui.frame_table_view import display_frame

    display_frame(frame, rows=20, tail=False, decimals=5)

Unlike `ui.bar_window_view` (built for `BarWindow`'s constant-memory
streaming), this operates on a frame already fully materialized in memory --
selecting first/last/all rows is a plain `head`/`tail`/no-op slice. Reuses
`ui.bar_window_view.format_table` for the actual column alignment, since that
helper is Bar-agnostic.
"""

import pandas as pd

from ui.bar_window_view import format_table


def display_frame(frame, *, rows, tail, decimals):
    """Print the bar table's label, its rows, and any truncation note.

    `rows=None` shows every row in `frame`; otherwise the first `rows` rows,
    or the last `rows` when `tail` is set.
    """
    total_count = len(frame)

    if rows is None:
        visible = frame
        label = "all bars"
    elif tail:
        visible = frame.tail(rows)
        label = f"last {len(visible)} bars"
    else:
        visible = frame.head(rows)
        label = f"first {len(visible)} bars"

    print("")
    print(f"--- {label} ---")

    header, table_rows = build_rows(visible, decimals)

    for line in format_table(header, table_rows):
        print(line)

    hidden_count = total_count - len(visible)
    if hidden_count > 0:
        print(f"... {hidden_count:,} more bars (use --all, or --rows N)")


def build_rows(frame, decimals):
    """Turn frame rows into aligned text columns, dropping columns nothing uses."""
    header = ["DATE", "TIME", "OPEN", "HIGH", "LOW", "CLOSE", "TICKVOL"]

    has_volume = "volume" in frame.columns and (frame["volume"] != 0).any()
    has_spread = "spread" in frame.columns and frame["spread"].notna().any()

    if has_volume:
        header.append("VOL")

    if has_spread:
        header.append("SPREAD")

    rows = []

    for row in frame.itertuples(index=False):
        line = [
            row.datetime.strftime("%Y.%m.%d"),
            row.datetime.strftime("%H:%M"),
            f"{row.open:.{decimals}f}",
            f"{row.high:.{decimals}f}",
            f"{row.low:.{decimals}f}",
            f"{row.close:.{decimals}f}",
            f"{row.tick_volume:,}",
        ]

        if has_volume:
            line.append(f"{row.volume:,}")

        if has_spread:
            spread = row.spread
            line.append("" if pd.isna(spread) else str(int(spread)))

        rows.append(line)

    return header, rows
