"""Tests for `backtest.run_backtest`."""

from datetime import datetime

from backtest import run_backtest
from domain.backtesting.backtest import Backtest
from ports.run_environment import GitCommit
from tests.domain.backtesting.backtest._fakes import ScriptedStrategy, data


def test_runs_records_and_writes(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0, 1]), data(10, {0: "win"})), tmp_path, source="clean.csv")

    assert run.result.statistics.loc["all", "trades"] == 2
    assert run.provenance.source == "clean.csv"
    assert [p.name for p in run.paths] == ["positions.csv", "statistics.txt", "statistics.csv", "run.json"]


def test_the_report_is_the_written_statistics_txt(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0]), data(10, {})), tmp_path)

    assert (tmp_path / "statistics.txt").read_text() == run.report


def test_the_strategy_name_reaches_the_record_and_the_report(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0]), data(10, {})), tmp_path, strategy_name="scripted")

    assert run.provenance.strategy_name == "scripted"
    assert "BACKTEST -- scripted" in run.report


def test_records_the_clock_and_git_state_given(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0]), data(10, {})), tmp_path,
                       now=lambda: datetime(2026, 3, 4, 5, 6, 7), git_commit=lambda: GitCommit("abc1234", dirty=True))

    assert run.provenance.created == datetime(2026, 3, 4, 5, 6, 7)
    assert run.provenance.git == GitCommit("abc1234", dirty=True)


def test_reads_the_real_clock_and_repo_by_default(tmp_path) -> None:
    run = run_backtest(Backtest(ScriptedStrategy([0]), data(10, {})), tmp_path)

    assert isinstance(run.provenance.created, datetime)
    assert isinstance(run.provenance.git, GitCommit)
