"""Tests for `libs.metatrader_csv.export_layout.sniff_layout`."""

from pathlib import Path

import pytest

from libs.metatrader_csv import AmbiguousLayoutError, Layout, sniff_layout

from .._fakes import EIGHTH_IS_SPREAD, HEADERLESS_7, HEADERLESS_8, MT5_HEADER_9, write_csv


def test_an_mt5_header(tmp_path: Path) -> None:
    layout = sniff_layout(write_csv(tmp_path, MT5_HEADER_9))

    assert layout == Layout(delimiter="\t", has_header=True, field_count=9, columns={
        "date": 0, "time": 1, "open": 2, "high": 3, "low": 4, "close": 5, "tick_volume": 6, "volume": 7, "spread": 8})


def test_a_plain_header_with_aliases_in_any_order(tmp_path: Path) -> None:
    layout = sniff_layout(write_csv(tmp_path, "Date;Time;C;O;H;L;Real Volume\n"))

    assert layout.delimiter == ";"
    assert layout.columns == {"date": 0, "time": 1, "close": 2, "open": 3, "high": 4, "low": 5, "volume": 6}


@pytest.mark.parametrize("width, last", [(6, "close"), (7, "tick_volume"), (9, "spread")])
def test_headerless_widths_follow_metatrader_order(tmp_path: Path, width: int, last: str) -> None:
    fields = ["2020.01.02", "00:00", "1.1", "1.2", "1.0", "1.15", "10", "0", "2"][:width]

    layout = sniff_layout(write_csv(tmp_path, ",".join(fields) + "\n"))

    assert (layout.has_header, layout.field_count) == (False, width)
    assert max(layout.columns, key=layout.columns.get) == last


def test_extra_columns_past_nine_are_ignored(tmp_path: Path) -> None:
    layout = sniff_layout(write_csv(tmp_path, "2020.01.02,00:00,1.1,1.2,1.0,1.15,10,0,2,99\n"))

    assert layout.columns["spread"] == 8 and len(layout.columns) == 9


def test_eight_headerless_columns_are_ambiguous(tmp_path: Path) -> None:
    with pytest.raises(AmbiguousLayoutError, match="8-column export is ambiguous"):
        sniff_layout(write_csv(tmp_path, HEADERLESS_8))


def test_headerless_layouts_settle_the_ambiguity(tmp_path: Path) -> None:
    layout = sniff_layout(write_csv(tmp_path, HEADERLESS_8), headerless_layouts=EIGHTH_IS_SPREAD)

    assert layout.columns["spread"] == 7 and "volume" not in layout.columns


def test_headerless_layouts_can_override_a_standard_width(tmp_path: Path) -> None:
    custom = {7: ("date", "time", "open", "high", "low", "close", "spread")}

    layout = sniff_layout(write_csv(tmp_path, HEADERLESS_7), headerless_layouts=custom)

    assert layout.columns["spread"] == 6 and "tick_volume" not in layout.columns


def test_a_header_without_prices_falls_back_to_positions(tmp_path: Path) -> None:
    layout = sniff_layout(write_csv(tmp_path, "<DATE>,<TIME>,<A>,<B>,<C>,<D>,<E>\n"))

    assert layout.has_header
    assert layout.columns["tick_volume"] == 6


def test_leading_blank_lines_are_skipped(tmp_path: Path) -> None:
    assert sniff_layout(write_csv(tmp_path, "\n\n" + HEADERLESS_7)).field_count == 7


def test_an_empty_file_is_none(tmp_path: Path) -> None:
    assert sniff_layout(write_csv(tmp_path, "")) is None
