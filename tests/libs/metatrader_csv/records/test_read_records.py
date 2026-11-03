"""Tests for `libs.metatrader_csv.records.read_records`."""

from pathlib import Path

import pytest

from libs.metatrader_csv import MetatraderParseError, iterate_records, read_records

from .._fakes import EIGHTH_IS_VOLUME, HEADERLESS_8, MT5_HEADER_9, WITH_BAD_ROW, write_csv


def test_the_records_of_iterate_records_as_a_list(tmp_path: Path) -> None:
    path = write_csv(tmp_path, MT5_HEADER_9)

    assert read_records(path) == list(iterate_records(path))


def test_passes_its_options_through(tmp_path: Path) -> None:
    skipped = []

    assert len(read_records(write_csv(tmp_path, WITH_BAD_ROW), strict=False,
                            on_skip=lambda *call: skipped.append(call))) == 2
    assert len(skipped) == 1
    assert read_records(write_csv(tmp_path, HEADERLESS_8, "8.csv"), headerless_layouts=EIGHTH_IS_VOLUME)[0].volume == 7

    with pytest.raises(MetatraderParseError):
        read_records(write_csv(tmp_path, WITH_BAD_ROW, "bad.csv"))
