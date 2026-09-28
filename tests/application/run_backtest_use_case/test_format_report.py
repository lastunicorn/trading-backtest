"""Tests for `application.run_backtest_use_case.format_report`."""

from application.run_backtest_use_case import build_run_info, format_report
from domain.pandas_approach.backtest import Backtest
from tests.domain.pandas_approach.backtest._fakes import ScriptedStrategy, data


def _report(entry_days, results, *, source=None, **kwargs) -> str:
    backtest = Backtest(ScriptedStrategy(entry_days), data(10, results), **kwargs)
    result = backtest.run()
    return format_report(result, build_run_info(backtest, result, source=source))


def _row(report: str, metric: str) -> list[str]:
    [line] = [line for line in report.splitlines() if line.startswith(metric + " ")]
    return line.split()[1:]


def test_header_names_strategy_data_and_settings() -> None:
    report = _report([0], {})

    assert "BACKTEST -- ScriptedStrategy" in report
    assert "entry_days=[0]" in report
    assert "EURUSD 5m, 60 bars" in report
    assert "FixedCost(pips=1.7)" in report
    assert "ambiguous bars exclude" in report


def test_one_column_per_split() -> None:
    header = next(line for line in _report([0], {}).splitlines() if "discovery" in line and "test" in line)

    assert header.split() == ["all", "discovery", "validation", "test"]


def test_cells_are_formatted_by_metric_kind() -> None:
    report = _report([0, 1], {0: "win", 1: "loss"})

    assert _row(report, "trades") == ["2", "2", "0", "0"]
    assert _row(report, "win_rate_pct") == ["50.0%", "50.0%", "n/a", "n/a"]
    assert _row(report, "total_net_pips")[0] == "-3.4"
    assert _row(report, "profit_factor")[0] == "0.84"


def test_profit_factor_without_losses_reads_inf() -> None:
    assert _row(_report([0], {0: "win"}), "profit_factor")[0] == "inf"


def test_verdict_requires_net_profit_in_every_split() -> None:
    all_win = _report([0, 6, 8], {0: "win", 6: "win", 8: "win"})
    test_loses = _report([0, 6, 8], {0: "win", 6: "win", 8: "loss"})

    assert "Net positive in every split (discovery, validation, test): yes" in all_win
    assert "Net positive in every split (discovery, validation, test): no" in test_loses


def test_source_line_appears_only_when_recorded() -> None:
    assert "Source:" not in _report([0], {})
    assert "Source:      clean.csv" in _report([0], {}, source="clean.csv")


def test_without_splits_there_is_no_verdict() -> None:
    assert "Net positive" not in _report([0], {}, splits=False)
