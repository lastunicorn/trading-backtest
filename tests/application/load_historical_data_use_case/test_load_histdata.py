"""Tests for `application.load_historical_data_use_case.load_histdata`."""

from zoneinfo import ZoneInfo

import pytest

from application.load_historical_data_use_case import load_histdata
from domain.market_data.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ
from domain.market_data.sample_size import SampleSize
from domain.market_data.symbol import EURUSD

from ._fakes import START, write_histdata_export

M5 = SampleSize.Parse("5m")


def test_one_download_is_resampled_to_the_timeframe(tmp_path) -> None:
    data = load_histdata(write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv"), M5, EURUSD, timezone=HISTDATA_TZ)

    assert len(data) == 2
    first = data.data.iloc[0]
    assert first["datetime"] == START
    assert (first["open"], first["high"], first["low"], first["close"]) == pytest.approx((1.1000, 1.1006, 1.0998, 1.1005))


def test_there_is_no_volume_or_spread(tmp_path) -> None:
    data = load_histdata(write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv"), M5, EURUSD, timezone=HISTDATA_TZ)

    assert list(data.data.columns) == ["datetime", "open", "high", "low", "close"]


@pytest.mark.parametrize("zone", [HISTDATA_TZ, ZoneInfo("America/New_York"), ZoneInfo("UTC"), BROKER_SERVER_TZ])
def test_any_clock_labels_the_bars_unshifted(tmp_path, zone) -> None:
    data = load_histdata(write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv"), M5, EURUSD, timezone=zone)

    assert data.timezone == zone
    assert data.data["datetime"].iat[0] == START


def test_a_folder_reads_only_the_downloads_not_the_gap_reports(tmp_path) -> None:
    write_histdata_export(tmp_path / "DAT_MT_EURUSD_M1_202001.csv")
    (tmp_path / "DAT_MT_EURUSD_M1_202001.txt").write_text("HistData.com (c) 2012\nGap of 128s found\n")
    write_histdata_export(tmp_path / "notes.csv", n=20)  # not a histdata download

    assert len(load_histdata(tmp_path, M5, EURUSD, timezone=HISTDATA_TZ)) == 2
