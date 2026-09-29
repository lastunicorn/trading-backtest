"""Tests for `backtest.build_run_info`."""

from datetime import time
from zoneinfo import ZoneInfo

from backtest import build_run_info
from domain.broker_clock import BROKER_SERVER_TZ
from domain.pandas_approach.backtest import AmbiguityPolicy, Backtest, PositionCloseDelay
from domain.pandas_approach.cost_model import FixedCost
from domain.pandas_approach.splits import SplitMode
from strategies.rsi_divergence import RsiDivergence
from tests.domain.pandas_approach.backtest._fakes import ScriptedStrategy, data


def _info(backtest: Backtest, **kwargs) -> dict:
    return build_run_info(backtest, backtest.run(), **kwargs)


def test_records_the_strategy() -> None:
    strategy = _info(Backtest(ScriptedStrategy([0, 1]), data(10, {})))["strategy"]

    assert strategy["name"] == "ScriptedStrategy"
    assert strategy["parameters"] == {"entry_days": [0, 1]}
    assert strategy["class"].endswith("_fakes.ScriptedStrategy")


def test_records_timezone_aware_times_with_their_zone() -> None:
    strategy = RsiDivergence(start_time=time(8, 0, tzinfo=ZoneInfo("Europe/London")),
                             end_time=time(16, 30, tzinfo=BROKER_SERVER_TZ))

    parameters = _info(Backtest(strategy, data(10, {})))["strategy"]["parameters"]

    assert (parameters["start_time"], parameters["end_time"]) == ("08:00:00 Europe/London", "16:30:00 broker")


def test_records_the_data() -> None:
    assert _info(Backtest(ScriptedStrategy([0]), data(10, {})))["data"] == {
        "symbol": "EURUSD",
        "timeframe": "5m",
        "timezone": "broker-server (America/New_York+7h)",
        "first_bar": "2026-01-05T10:00:00",
        "last_bar": "2026-01-14T10:25:00",
        "bars": 60,
    }


def test_records_the_simulation_settings() -> None:
    backtest = Backtest(
        ScriptedStrategy([0]), data(10, {}), cost_model=FixedCost(pips=1.2),
        ambiguity_policy=AmbiguityPolicy.ASSUME_SL, position_resolve_delay=PositionCloseDelay.ENTRY_BAR, splits=SplitMode.YEARLY,
    )

    assert _info(backtest)["simulation"] == {
        "cost_model": {"class": "FixedCost", "pips": 1.2},
        "ambiguity_policy": "assume-sl",
        "position_resolve_delay": "entry-bar",
        "splits": "yearly",
    }


def test_records_trade_count_git_and_creation_time() -> None:
    info = _info(Backtest(ScriptedStrategy([0, 1]), data(10, {})))

    assert info["trades"] == 2
    assert set(info["git"]) == {"commit", "dirty"}
    assert "created" in info


def test_source_is_recorded_only_when_given() -> None:
    backtest = Backtest(ScriptedStrategy([0]), data(10, {}))

    assert "source" not in _info(backtest)
    assert _info(backtest, source="clean.csv")["source"] == "clean.csv"
