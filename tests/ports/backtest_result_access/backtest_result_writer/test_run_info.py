"""Tests for `ports.backtest_result_access.backtest_result_writer.run_info`."""

from dataclasses import replace
from datetime import datetime, time
from zoneinfo import ZoneInfo

from domain.market_data.broker_clock import BROKER_SERVER_TZ
from domain.backtesting.backtest import AmbiguityPolicy, Backtest
from domain.backtesting.cost_model import FixedCost
from domain.backtesting.splits import SplitMode
from domain.market_data.trading_session import LONDON_SESSION, TradingSession
from ports.backtest_result_access import run_info
from ports.run_environment import GitCommit
from strategies.orb_break_entry import OrbBreakEntry
from strategies.rsi_divergence import RsiDivergence
from tests.domain.backtesting.backtest._fakes import NotedCost, data

from ._fakes import PROVENANCE, result


def _parameters(strategy) -> dict:
    return run_info(Backtest(strategy, data(10, {})).run(), PROVENANCE)["strategy"]["parameters"]


def test_records_the_strategy() -> None:
    strategy = run_info(result([0, 1]), PROVENANCE)["strategy"]

    assert strategy["name"] == "ScriptedStrategy"
    assert strategy["parameters"] == {"entry_days": [0, 1]}
    assert strategy["class"].endswith("_fakes.ScriptedStrategy")


def test_records_the_given_strategy_name_instead_of_the_class_name() -> None:
    strategy = run_info(result(), replace(PROVENANCE, strategy_name="scripted"))["strategy"]

    assert strategy["name"] == "scripted"
    assert strategy["class"].endswith("_fakes.ScriptedStrategy")


def test_records_timezone_aware_times_with_their_zone() -> None:
    parameters = _parameters(RsiDivergence(start_time=time(8, 0, tzinfo=ZoneInfo("Europe/London")),
                                           end_time=time(16, 30, tzinfo=BROKER_SERVER_TZ)))

    assert (parameters["start_time"], parameters["end_time"]) == ("08:00:00 Europe/London", "16:30:00 broker")


def test_records_a_standard_session_by_name() -> None:
    assert _parameters(OrbBreakEntry(session=LONDON_SESSION))["session"] == "London"


def test_records_another_session_by_its_bounds() -> None:
    london = ZoneInfo("Europe/London")
    session = TradingSession(time(8, 0, tzinfo=london), time(17, 0, tzinfo=london), name="FX London")

    assert _parameters(OrbBreakEntry(session=session))["session"] == {
        "start_time": "08:00:00 Europe/London", "end_time": "17:00:00 Europe/London", "name": "FX London"}


def test_records_the_data() -> None:
    assert run_info(result(), PROVENANCE)["data"] == {
        "symbol": "EURUSD",
        "timeframe": "5m",
        "timezone": "broker-server (America/New_York+7h)",
        "first_bar": "2026-01-05T10:00:00",
        "last_bar": "2026-01-14T10:25:00",
        "bars": 60,
    }


def test_records_the_simulation_settings() -> None:
    simulated = result(cost_model=FixedCost(pips=1.2), ambiguity_policy=AmbiguityPolicy.ASSUME_SL)

    assert run_info(simulated, PROVENANCE)["simulation"] == {
        "cost_model": {"class": "FixedCost", "pips": 1.2},
        "ambiguity_policy": "assume-sl",
    }


def test_records_the_split_mode_beside_the_simulation() -> None:
    assert run_info(result(splits=SplitMode.YEARLY), PROVENANCE)["splits"] == "yearly"


def test_records_the_trade_count() -> None:
    assert run_info(result([0, 1]), PROVENANCE)["trades"] == 2


def test_records_the_creation_time_to_the_second() -> None:
    info = run_info(result(), replace(PROVENANCE, created=datetime(2026, 3, 4, 5, 6, 7, 890)))

    assert info["created"] == "2026-03-04T05:06:07"


def test_records_the_git_commit() -> None:
    info = run_info(result(), replace(PROVENANCE, git=GitCommit("abc1234", dirty=True)))

    assert info["git"] == {"commit": "abc1234", "dirty": True}


def test_records_unknown_git_state_as_none() -> None:
    info = run_info(result(), replace(PROVENANCE, git=GitCommit(None, dirty=None)))

    assert info["git"] == {"commit": None, "dirty": None}


def test_source_is_recorded_only_when_given() -> None:
    assert "source" not in run_info(result(), PROVENANCE)
    assert run_info(result(), replace(PROVENANCE, source="clean.csv"))["source"] == "clean.csv"


def test_notes_are_recorded_only_when_there_are_some() -> None:
    assert "notes" not in run_info(result(), PROVENANCE)
    assert run_info(result(cost_model=NotedCost("a note")), PROVENANCE)["notes"] == ["a note"]


def test_keys_are_in_record_order() -> None:
    info = run_info(result(cost_model=NotedCost("a note")), replace(PROVENANCE, source="clean.csv"))

    assert list(info) == ["created", "strategy", "data", "simulation", "splits", "trades", "git", "source", "notes"]
