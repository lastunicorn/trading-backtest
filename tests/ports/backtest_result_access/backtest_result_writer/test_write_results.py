"""Tests for `ports.backtest_result_access.backtest_result_writer.write_results`."""

import json
from dataclasses import replace

import pandas as pd

from domain.backtesting.splits import SplitMode
from domain.market_data.symbol import XAUUSD
from ports.backtest_result_access import format_report, run_info, write_results

from ._fakes import PROVENANCE, result


def _result(entry_days=(0, 1), results=None):
    return result(entry_days, results or {0: "win", 1: "loss"}, splits=SplitMode.DVT)


def _with_open_prices(original, *prices: float):
    trades = original.trades.copy()
    trades["open_price"] = list(prices)
    return replace(original, trades=trades)


def test_writes_the_four_result_files_creating_the_directory(tmp_path) -> None:
    paths = write_results(_result(), PROVENANCE, tmp_path / "new" / "out")

    assert [p.name for p in paths] == ["positions.csv", "statistics.txt", "statistics.csv", "run.json"]
    assert all(p.is_file() for p in paths)


def test_positions_file_has_one_row_per_trade_with_rounded_pips(tmp_path) -> None:
    write_results(_result(), PROVENANCE, tmp_path)

    positions = pd.read_csv(tmp_path / "positions.csv")
    assert positions["outcome"].tolist() == ["take-profit-hit", "stop-loss-hit"]
    assert positions["net_pips"].tolist() == [18.3, -21.7]
    assert positions["split"].tolist() == ["discovery", "discovery"]


def test_prices_are_rounded_to_the_symbol_precision(tmp_path) -> None:
    eurusd = _with_open_prices(_result(), 1.1234567, 1.1)
    gold = replace(eurusd, data=replace(eurusd.data, symbol=XAUUSD))

    write_results(eurusd, PROVENANCE, tmp_path / "eurusd")
    write_results(gold, PROVENANCE, tmp_path / "gold")

    assert pd.read_csv(tmp_path / "eurusd" / "positions.csv")["open_price"].tolist() == [1.12346, 1.1]
    assert pd.read_csv(tmp_path / "gold" / "positions.csv")["open_price"].tolist() == [1.12, 1.1]


def test_statistics_csv_has_one_row_per_split(tmp_path) -> None:
    write_results(_result(), PROVENANCE, tmp_path)

    stats = pd.read_csv(tmp_path / "statistics.csv", index_col="split")
    assert stats.index.tolist() == ["all", "discovery", "validation", "test"]
    assert stats.loc["all", "trades"] == 2


def test_report_and_run_info_are_written_as_formatted(tmp_path) -> None:
    written = _result()

    write_results(written, PROVENANCE, tmp_path)

    assert (tmp_path / "statistics.txt").read_text() == format_report(written, PROVENANCE)
    assert json.loads((tmp_path / "run.json").read_text()) == run_info(written, PROVENANCE)


def test_run_info_is_indented_with_one_tab_per_level_and_ends_with_a_newline(tmp_path) -> None:
    write_results(_result(), PROVENANCE, tmp_path)

    text = (tmp_path / "run.json").read_text()
    lines = text.splitlines()
    assert lines[2] == '\t"strategy": {'
    assert lines[3] == '\t\t"name": "ScriptedStrategy",'
    assert text.endswith("}\n")


def test_rewriting_replaces_earlier_results(tmp_path) -> None:
    write_results(_result(entry_days=(0, 1, 2)), PROVENANCE, tmp_path)
    write_results(_result(), PROVENANCE, tmp_path)

    assert len(pd.read_csv(tmp_path / "positions.csv")) == 2
