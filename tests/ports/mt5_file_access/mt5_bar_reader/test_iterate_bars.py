"""Tests for `ports.mt5_file_access.mt5_bar_reader.iterate_bars`."""

from datetime import datetime
from pathlib import Path

import pytest

from ports.mt5_file_access import Bar, BarParseError, iterate_bars

from ._fakes import HEADERLESS_7, MT5_HEADER_9, SEMICOLON_8, WITH_BAD_ROW, write_csv


def test_a_headerless_export_with_a_blank_tick_volume(tmp_path: Path) -> None:
    bars = list(iterate_bars(str(write_csv(tmp_path, HEADERLESS_7))))

    assert bars == [
        Bar(datetime(2020, 1, 2, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=10, real_volume=0, spread=None),
        Bar(datetime(2020, 1, 2, 0, 1), 1.15, 1.25, 1.1, 1.2, tick_volume=0, real_volume=0, spread=None),
    ]


def test_an_mt5_header_with_seconds_volume_and_a_blank_spread(tmp_path: Path) -> None:
    bars = list(iterate_bars(str(write_csv(tmp_path, MT5_HEADER_9))))

    assert bars == [
        Bar(datetime(2026, 7, 1, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=17, real_volume=0, spread=20),
        Bar(datetime(2026, 7, 1, 0, 1), 1.1, 1.2, 1.0, 1.15, tick_volume=14, real_volume=5, spread=None),
    ]


def test_a_headerless_eight_column_export_ends_in_spread(tmp_path: Path) -> None:
    bars = list(iterate_bars(str(write_csv(tmp_path, SEMICOLON_8))))

    assert [(bar.tick_volume, bar.real_volume, bar.spread) for bar in bars] == [(10, 0, 7), (10, 0, 8)]


def test_a_lowercase_header(tmp_path: Path) -> None:
    path = write_csv(tmp_path, "date,time,open,high,low,close,tick_volume\n2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n")

    assert [bar.tick_volume for bar in iterate_bars(str(path))] == [10]


def test_strict_raises_on_the_first_bad_line_with_its_exact_number(tmp_path: Path) -> None:
    path = write_csv(tmp_path, WITH_BAD_ROW)

    with pytest.raises(BarParseError) as raised:
        list(iterate_bars(str(path)))

    assert (raised.value.line_no, raised.value.line) == (3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3")
    assert str(raised.value) == ("export.csv:3: could not convert string to float: 'bad'"
                                 "  |  2020.01.02,00:02,bad,1.2,1.0,1.1,3")


def test_not_strict_skips_bad_lines_and_reports_them(tmp_path: Path) -> None:
    skipped = []

    bars = list(iterate_bars(str(write_csv(tmp_path, WITH_BAD_ROW)), strict=False,
                             on_skip=lambda *call: skipped.append(call)))

    assert [bar.dt.minute for bar in bars] == [0, 3]
    assert bars[1].tick_volume == 4
    assert skipped == [(3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "could not convert string to float: 'bad'")]


def test_a_row_missing_prices_is_reported(tmp_path: Path) -> None:
    skipped = []
    path = write_csv(tmp_path, "2020.01.02,00:00,1.1,1.2,1.0,1.15,10\n2020.01.02,00:01,1.1,1.2\n")

    list(iterate_bars(str(path), strict=False, on_skip=lambda *call: skipped.append(call)))

    assert skipped == [(2, "2020.01.02,00:01,1.1,1.2", "missing field(s): low, close")]


def test_an_empty_file_has_no_bars(tmp_path: Path) -> None:
    assert list(iterate_bars(str(write_csv(tmp_path, "")))) == []
