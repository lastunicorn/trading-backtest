"""Tests for `backtest.write_results`."""

import json

import pandas as pd

from backtest import write_results
from domain.pandas_approach.backtest import Backtest
from domain.pandas_approach.splits import SplitMode
from tests.domain.pandas_approach.backtest._fakes import ScriptedStrategy, data

RUN_INFO = {"strategy": {"name": "ScriptedStrategy"}, "source": "somewhere.csv"}


def _write(out_dir, entry_days=(0, 1), results=None, price_decimals=5):
    result = Backtest(ScriptedStrategy(list(entry_days)), data(10, results or {0: "win", 1: "loss"}),
                      splits=SplitMode.DVT).run()
    return write_results(result, RUN_INFO, "the report\n", out_dir, price_decimals=price_decimals)


def test_writes_the_four_result_files_creating_the_directory(tmp_path) -> None:
    paths = _write(tmp_path / "new" / "out")

    assert [p.name for p in paths] == ["positions.csv", "statistics.txt", "statistics.csv", "run.json"]
    assert all(p.is_file() for p in paths)


def test_positions_file_has_one_row_per_trade_with_rounded_pips(tmp_path) -> None:
    _write(tmp_path)

    positions = pd.read_csv(tmp_path / "positions.csv")
    assert positions["outcome"].tolist() == ["take-profit-hit", "stop-loss-hit"]
    assert positions["net_pips"].tolist() == [18.3, -21.7]
    assert positions["split"].tolist() == ["discovery", "discovery"]


def test_prices_are_rounded_to_the_given_precision(tmp_path) -> None:
    _write(tmp_path, price_decimals=2)

    assert pd.read_csv(tmp_path / "positions.csv")["open_price"].tolist() == [1.1, 1.1]


def test_statistics_csv_has_one_row_per_split(tmp_path) -> None:
    _write(tmp_path)

    stats = pd.read_csv(tmp_path / "statistics.csv", index_col="split")
    assert stats.index.tolist() == ["all", "discovery", "validation", "test"]
    assert stats.loc["all", "trades"] == 2


def test_report_and_run_info_are_written_as_given(tmp_path) -> None:
    _write(tmp_path)

    assert (tmp_path / "statistics.txt").read_text() == "the report\n"
    assert json.loads((tmp_path / "run.json").read_text()) == RUN_INFO


def test_run_info_is_indented_with_one_tab_per_level(tmp_path) -> None:
    _write(tmp_path)

    lines = (tmp_path / "run.json").read_text().splitlines()
    assert lines[1] == '\t"strategy": {'
    assert lines[2] == '\t\t"name": "ScriptedStrategy"'


def test_rewriting_replaces_earlier_results(tmp_path) -> None:
    _write(tmp_path, entry_days=(0, 1, 2))
    _write(tmp_path)

    assert len(pd.read_csv(tmp_path / "positions.csv")) == 2
