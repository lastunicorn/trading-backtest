"""Tests for `ports.mt5_file_access.mt5_bar_reader.read_bars`."""

from pathlib import Path

import pytest

from ports.mt5_file_access import BarParseError, iterate_bars, read_bars

from ._fakes import MT5_HEADER_9, WITH_BAD_ROW, write_csv


def test_the_same_bars_as_iterate_bars_in_a_list(tmp_path: Path) -> None:
    path = str(write_csv(tmp_path, MT5_HEADER_9))

    assert read_bars(path) == list(iterate_bars(path))


def test_strict_by_default(tmp_path: Path) -> None:
    with pytest.raises(BarParseError):
        read_bars(str(write_csv(tmp_path, WITH_BAD_ROW)))


def test_passes_on_skip_through(tmp_path: Path) -> None:
    skipped = []

    bars = read_bars(str(write_csv(tmp_path, WITH_BAD_ROW)), strict=False, on_skip=lambda *call: skipped.append(call))

    assert len(bars) == 2
    assert [call[0] for call in skipped] == [3]
