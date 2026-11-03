"""Tests for `ports.histdata_file_access.histdata_frame_reader.read_frame`."""

from pathlib import Path

import pandas as pd
import pytest

from libs.metatrader_csv import MetatraderParseError
from ports.histdata_file_access import FILE_PATTERN, FRAME_COLUMNS, read_frame

DOWNLOAD = (
    "2025.01.01,17:00,1.035030,1.035140,1.035030,1.035140,0\n"
    "2025.01.01,17:02,1.035140,1.035150,1.035100,1.035120,0\n"
)

REAL_DOWNLOADS = Path("/nfs/YubabaFinance/trading/historical data/histdata/mt/2025")


def _write(folder: Path, text: str, name: str = "DAT_MT_EURUSD_M1_202501.csv") -> Path:
    path = folder / name
    path.write_text(text)
    return path


def test_prices_are_read_and_the_zero_volume_is_dropped(tmp_path: Path) -> None:
    frame = read_frame(_write(tmp_path, DOWNLOAD))

    assert list(frame.columns) == ["datetime", *FRAME_COLUMNS]
    assert {column: str(dtype) for column, dtype in frame.dtypes.items() if column != "datetime"} == dict.fromkeys(
        FRAME_COLUMNS, "float64")
    assert list(frame["datetime"]) == [pd.Timestamp("2025-01-01 17:00"), pd.Timestamp("2025-01-01 17:02")]
    assert tuple(frame.iloc[1][list(FRAME_COLUMNS)]) == pytest.approx((1.03514, 1.03515, 1.0351, 1.03512))


def test_an_empty_file_gives_the_columns_and_no_rows(tmp_path: Path) -> None:
    frame = read_frame(_write(tmp_path, ""))

    assert list(frame.columns) == ["datetime", *FRAME_COLUMNS]
    assert frame.empty


def test_a_malformed_line_raises_by_default(tmp_path: Path) -> None:
    with pytest.raises(MetatraderParseError):
        read_frame(_write(tmp_path, DOWNLOAD + "2025.01.01,17:03,bad,1.0,1.0,1.0,0\n"))


def test_not_strict_drops_a_malformed_line_and_reports_it(tmp_path: Path) -> None:
    skipped = []

    frame = read_frame(_write(tmp_path, DOWNLOAD + "2025.01.01,17:03,bad,1.0,1.0,1.0,0\n"), strict=False,
                       on_skip=lambda line_no, line, reason: skipped.append(line_no))

    assert len(frame) == 2
    assert skipped == [3]


def test_the_file_pattern_matches_downloads_not_gap_reports() -> None:
    assert Path("DAT_MT_EURUSD_M1_202501.csv").match(FILE_PATTERN)
    assert not Path("DAT_MT_EURUSD_M1_202501.txt").match(FILE_PATTERN)


@pytest.mark.skipif(not REAL_DOWNLOADS.is_dir(), reason="local histdata archive not mounted")
def test_a_real_download_starts_at_the_new_york_week_open() -> None:
    frame = read_frame(REAL_DOWNLOADS / "DAT_MT_EURUSD_M1_202501.csv")

    assert list(frame.columns) == ["datetime", *FRAME_COLUMNS]
    assert frame["datetime"].iat[0] == pd.Timestamp("2025-01-01 17:00")
