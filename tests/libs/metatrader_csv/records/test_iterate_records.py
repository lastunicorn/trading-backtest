"""Tests for `libs.metatrader_csv.records.iterate_records`."""

from datetime import datetime
from pathlib import Path

import pytest

from libs.metatrader_csv import AmbiguousLayoutError, MetatraderParseError, MetatraderRecord, iterate_records

from .._fakes import EIGHTH_IS_VOLUME, HEADERLESS_7, HEADERLESS_8, MT5_HEADER_9, WITH_BAD_ROW, write_csv


def test_blank_and_absent_fields_are_none(tmp_path: Path) -> None:
    records = list(iterate_records(write_csv(tmp_path, HEADERLESS_7)))

    assert records == [
        MetatraderRecord(datetime(2020, 1, 2, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=10),
        MetatraderRecord(datetime(2020, 1, 2, 0, 1), 1.15, 1.25, 1.1, 1.2),
    ]


def test_an_mt5_header_with_seconds_and_a_float_count(tmp_path: Path) -> None:
    records = list(iterate_records(write_csv(tmp_path, MT5_HEADER_9)))

    assert records == [
        MetatraderRecord(datetime(2026, 7, 1, 0, 0), 1.1, 1.2, 1.0, 1.15, tick_volume=17, volume=0, spread=20),
        MetatraderRecord(datetime(2026, 7, 1, 0, 1), 1.1, 1.2, 1.0, 1.15, tick_volume=14, volume=5, spread=None),
    ]


def test_headerless_layouts_name_the_eighth_column(tmp_path: Path) -> None:
    records = list(iterate_records(write_csv(tmp_path, HEADERLESS_8), headerless_layouts=EIGHTH_IS_VOLUME))

    assert [(r.tick_volume, r.volume, r.spread) for r in records] == [(10, 7, None), (10, 8, None)]


def test_an_ambiguous_layout_raises_even_when_not_strict(tmp_path: Path) -> None:
    with pytest.raises(AmbiguousLayoutError):
        list(iterate_records(write_csv(tmp_path, HEADERLESS_8), strict=False))


def test_strict_raises_with_the_exact_line(tmp_path: Path) -> None:
    with pytest.raises(MetatraderParseError) as raised:
        list(iterate_records(write_csv(tmp_path, WITH_BAD_ROW)))

    assert (raised.value.line_no, raised.value.reason) == (3, "could not convert string to float: 'bad'")


def test_not_strict_skips_and_reports_exact_lines(tmp_path: Path) -> None:
    skipped = []

    records = list(iterate_records(write_csv(tmp_path, WITH_BAD_ROW), strict=False,
                                   on_skip=lambda *call: skipped.append(call)))

    assert [r.dt.minute for r in records] == [0, 3]
    assert skipped == [(3, "2020.01.02,00:02,bad,1.2,1.0,1.1,3", "could not convert string to float: 'bad'")]


@pytest.mark.parametrize("line, reason", [
    ("2020.01.02,00:00,1.1,1.2\n", "missing field(s): low, close"),
    ("2020-01-02,00:00,1.1,1.2,1.0,1.15\n", "unrecognized timestamp '2020-01-02 00:00'"),
])
def test_reasons_for_a_bad_line(tmp_path: Path, line: str, reason: str) -> None:
    skipped = []
    path = write_csv(tmp_path, "date,time,open,high,low,close\n" + line)

    list(iterate_records(path, strict=False, on_skip=lambda *call: skipped.append(call)))

    assert skipped == [(2, line.strip(), reason)]


def test_an_empty_file_has_no_records(tmp_path: Path) -> None:
    assert list(iterate_records(write_csv(tmp_path, ""))) == []
