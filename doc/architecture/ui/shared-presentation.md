# Shared presentation

Part of the [UI](README.md) of the [application blueprint](../README.md).

*Python: `ui/`.*

## `timezone_arg`

*`ui/cli_args.py`.* An argument-parser type: `timezone_by_name(text)`, or a usage error `unknown timezone '{name}': expected 'broker', 'histdata' or an IANA name such as 'UTC' or 'Europe/London'`.

## `format_table`

*`ui/text_table.py`.* `format_table(header: List<String>, rows: List<List<String>>, left_align: Set<Integer> = {}) -> List<String>`:

1. Each column's width is the longest of its header and cells.
2. Cells are right-aligned to the width, except the columns in `left_align`.
3. Lines: the header; a rule of `-` the width of each column; then the rows. Columns are separated by two spaces.

## `display_frame`

*`ui/frame_table_view.py`.* `display_frame(table, rows: Integer?, tail: Boolean, decimals: Integer?)` prints a bar table:

1. A blank line, then `--- first {k} bars ---`, `--- last {k} bars ---` (with `tail`) or `--- all bars ---` (`rows` is `null`), where `k` is the number shown.
2. A [`format_table`](#format_table) of the bars shown, columns:

   | Column | Shown when | Cell |
   |---|---|---|
   | `DATE`, `TIME` | always | `YYYY.MM.DD`, `HH:MM` |
   | `OPEN`, `HIGH`, `LOW`, `CLOSE` | always | `decimals` places, or the default number formatting |
   | `TICKVOL` | the table has `tick_volume` | thousands separators |
   | `VOL` | some `volume` is non-zero | thousands separators |
   | `SPREAD` | some `spread` is not null | rounded to a whole number (half to even), blank when null |

3. When bars are hidden: `... {n} more bars (use --all, or --rows N)`.

## The backtest report

`format_report` (*`backtest.py`*) lays out `statistics.txt`, which is also what the `backtest` CLI prints. Its exact layout is in [external-formats.md](../external-formats.md#statisticstxt).
