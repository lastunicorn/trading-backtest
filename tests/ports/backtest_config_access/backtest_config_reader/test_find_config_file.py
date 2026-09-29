"""Tests for `ports.backtest_config_access.backtest_config_reader.find_config_file`."""

import pytest

from ports.backtest_config_access import find_config_file


def test_a_file_is_used_as_given(tmp_path) -> None:
    config = tmp_path / "my_run.json"
    config.write_text("{}")

    assert find_config_file(config) == config


def test_a_folder_means_its_backtest_json(tmp_path) -> None:
    (tmp_path / "backtest.json").write_text("{}")

    assert find_config_file(tmp_path) == tmp_path / "backtest.json"


def test_a_folder_without_backtest_json_is_an_error(tmp_path) -> None:
    (tmp_path / "other.json").write_text("{}")

    with pytest.raises(FileNotFoundError, match="backtest.json"):
        find_config_file(tmp_path)


def test_a_missing_file_is_an_error(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        find_config_file(tmp_path / "nope.json")
