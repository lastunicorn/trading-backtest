"""Tests for `backtest.run_backtest`."""

import json

from backtest import run_backtest
from domain.pandas_approach.backtest import Backtest
from tests.domain.pandas_approach.backtest._fakes import ScriptedStrategy, data


def test_runs_records_and_writes(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0, 1]), data(10, {0: "win"})), tmp_path, source="clean.csv")

    assert run.result.statistics.loc["all", "trades"] == 2
    assert run.run_info["source"] == "clean.csv"
    assert [p.name for p in run.paths] == ["positions.csv", "statistics.txt", "statistics.csv", "run.json"]


def test_written_files_match_the_returned_run(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0]), data(10, {})), tmp_path)

    assert (tmp_path / "statistics.txt").read_text() == run.report
    assert json.loads((tmp_path / "run.json").read_text()) == json.loads(json.dumps(run.run_info, default=str))

