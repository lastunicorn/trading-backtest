"""Tests for `application.load_historical_data_use_case.load_source`."""

from zoneinfo import ZoneInfo

from application.load_historical_data_use_case import SourceFormat, load_source
from domain.broker_clock import BROKER_SERVER_TZ
from domain.sample_size import SampleSize
from domain.symbol import EurUsd

from ._fakes import write_dukascopy_month, write_histdata_export, write_mt5_export

M5 = SampleSize.Parse("5m")


def test_metatrader_format_reads_mt5_exports(tmp_path) -> None:
    data = load_source(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"), SourceFormat.METATRADER, M5, EurUsd(),
                       timezone=BROKER_SERVER_TZ)

    assert len(data) == 2
    assert "spread" in data.data.columns
    assert data.timezone == BROKER_SERVER_TZ


def test_dukascopy_format_reads_bid_ask_pairs(tmp_path) -> None:
    data = load_source(write_dukascopy_month(tmp_path), SourceFormat.DUKASCOPY, M5, EurUsd(), timezone=ZoneInfo("UTC"))

    assert len(data) == 2
    assert data.timezone == ZoneInfo("UTC")


def test_histdata_format_reads_histdata_downloads(tmp_path) -> None:
    data = load_source(write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv"), SourceFormat.HISTDATA, M5,
                       EurUsd(), timezone=ZoneInfo("America/New_York"))

    assert len(data) == 2
    assert data.timezone == ZoneInfo("America/New_York")
