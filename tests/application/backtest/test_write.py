"""Tests for `application.backtest.BacktestResult.write`."""

import json

import pandas as pd

from application.backtest import Backtest

from ._fakes import ScriptedStrategy, data


def _result():
    return Backtest(ScriptedStrategy([0, 1]), data(10, {0: "win", 1: "loss"})).run()


def test_writes_the_four_result_files(tmp_path) -> None:
    paths = _result().write(tmp_path / "out")

    assert [p.name for p in paths] == ["positions.csv", "statistics.txt", "statistics.csv", "run.json"]
    assert all(p.is_file() for p in paths)


def test_positions_file_has_one_row_per_trade_with_rounded_values(tmp_path) -> None:
    _result().write(tmp_path)

    positions = pd.read_csv(tmp_path / "positions.csv")
    assert len(positions) == 2
    assert positions["outcome"].tolist() == ["take-profit-hit", "stop-loss-hit"]
    assert positions["net_pips"].tolist() == [18.3, -21.7]
    assert positions["split"].tolist() == ["discovery", "discovery"]


def test_statistics_csv_has_one_row_per_split(tmp_path) -> None:
    _result().write(tmp_path)

    stats = pd.read_csv(tmp_path / "statistics.csv", index_col="split")
    assert stats.index.tolist() == ["all", "discovery", "validation", "test"]
    assert stats.loc["all", "trades"] == 2


def test_run_json_round_trips_the_run_info(tmp_path) -> None:
    result = _result()
    result.run_info["source"] = "somewhere.csv"

    result.write(tmp_path)

    assert json.loads((tmp_path / "run.json").read_text()) == json.loads(json.dumps(result.run_info, default=str))


def test_statistics_txt_is_the_report(tmp_path) -> None:
    result = _result()

    result.write(tmp_path)

    assert (tmp_path / "statistics.txt").read_text() == result.report()


def test_rewriting_replaces_earlier_results(tmp_path) -> None:
    Backtest(ScriptedStrategy([0, 1, 2]), data(10, {})).run().write(tmp_path)

    _result().write(tmp_path)

    assert len(pd.read_csv(tmp_path / "positions.csv")) == 2
