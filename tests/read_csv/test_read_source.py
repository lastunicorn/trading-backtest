"""Tests for `read_csv.read_source`."""

import pytest

from application.load_historical_data_use_case import SourceFormat
from domain.symbol import EURUSD
from ports.mt5_file_access import BarParseError
from read_csv import read_source
from tests.application.load_historical_data_use_case._fakes import (
    write_dukascopy_month,
    write_histdata_export,
    write_mt5_export,
)


def test_metatrader_reads_every_csv_in_a_folder_in_name_order(tmp_path) -> None:
    write_mt5_export(tmp_path / "EURUSD_2020_01.csv")
    write_mt5_export(tmp_path / "EURUSD_2020_02.csv", n=3)

    frame, file_count = read_source(tmp_path, SourceFormat.METATRADER)

    assert file_count == 2
    assert len(frame) == 13
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "tick_volume", "volume", "spread"]
    assert frame["spread"].iloc[0] == 5   # points, as exported


def test_histdata_reads_only_its_downloads_and_keeps_ohlc(tmp_path) -> None:
    write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv")
    (tmp_path / "notes.csv").write_text("not a download\n")

    frame, file_count = read_source(tmp_path, SourceFormat.HISTDATA)

    assert file_count == 1
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close"]


def test_dukascopy_drops_the_volumes_and_gives_the_spread_in_points(tmp_path) -> None:
    write_dukascopy_month(tmp_path, spread=0.00002)

    frame, file_count = read_source(tmp_path, SourceFormat.DUKASCOPY, symbol=EURUSD)

    assert file_count == 1
    assert list(frame.columns) == ["datetime", "open", "high", "low", "close", "spread"]
    assert (frame["spread"] == 2.0).all()   # 0.00002 at EURUSD's 0.00001 tick size


def test_a_malformed_line_is_skipped_and_reported_unless_strict(tmp_path) -> None:
    path = write_mt5_export(tmp_path / "EURUSD_2020_01.csv")
    path.write_text(path.read_text() + "garbage\n")
    skipped = []

    frame, _ = read_source(path, SourceFormat.METATRADER, strict=False,
                           on_skip=lambda line_no, line, reason: skipped.append(line_no))

    assert len(frame) == 10
    assert skipped == [11]
    with pytest.raises(BarParseError):
        read_source(path, SourceFormat.METATRADER, strict=True)


@pytest.mark.parametrize("source_format", [SourceFormat.METATRADER, SourceFormat.HISTDATA])
def test_a_folder_with_no_file_of_the_format_raises(tmp_path, source_format) -> None:
    with pytest.raises(FileNotFoundError):
        read_source(tmp_path, source_format)
