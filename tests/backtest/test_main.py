"""Tests for `backtest.main`."""

import sys

from backtest import main
from tests.ports.backtest_config_access.backtest_config_reader._fakes import data_source, write_config


def test_no_usable_source_files_is_a_one_line_error_not_a_traceback(tmp_path, monkeypatch, capsys) -> None:
    config = write_config(tmp_path, {"strategy": {"name": "rsi_divergence"},
                                     "data_source": data_source("no_such_folder"), "out": "results"})
    monkeypatch.setattr(sys, "argv", ["backtest.py", str(config)])

    assert main() == 1

    assert capsys.readouterr().err == "ERROR: No usable source files. See errors above.\n"
    assert not (tmp_path / "results").exists()
