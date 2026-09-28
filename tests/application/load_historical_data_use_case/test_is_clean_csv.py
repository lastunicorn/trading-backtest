"""Tests for `application.load_historical_data_use_case.is_clean_csv`."""

from application.load_historical_data_use_case import _is_clean_csv

from ._fakes import write_clean_csv, write_mt5_export


def test_datetime_header_is_a_clean_csv(tmp_path) -> None:
    assert _is_clean_csv(write_clean_csv(tmp_path / "clean.csv"))


def test_mt5_export_is_not(tmp_path) -> None:
    assert not _is_clean_csv(write_mt5_export(tmp_path / "EURUSD_2020_01.csv"))


def test_a_folder_is_not(tmp_path) -> None:
    assert not _is_clean_csv(tmp_path)
