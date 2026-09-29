"""Tests for `application.load_backtest_config_use_case.load_backtest_config`.

The shape checks (keys, JSON types, paths) are `read_config`'s and are tested
in tests/ports/backtest_config_access/backtest_config_reader/test_read_config.py.
"""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from application.load_backtest_config_use_case import load_backtest_config
from domain.broker_clock import BROKER_SERVER_TZ
from ports.backtest_config_access import BacktestConfig, DataConfig
from strategies import STRATEGIES
from strategies.rsi_divergence import RsiDivergence
from tests.ports.backtest_config_access.backtest_config_reader._fakes import data, write_config


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": "narrow_asia_fade", "data": data(),
                                                          "out": "results"}))

    assert config == BacktestConfig(
        strategy="narrow_asia_fade",
        data=DataConfig(source=tmp_path / "m5.csv", format="metatrader", symbol="EURUSD", timeframe="1m",
                        timezone="UTC"),
        out=tmp_path / "results",
        timeframe="5m",
    )


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    write_config(tmp_path, {"strategy": "rsi_divergence", "data": data("m1"), "out": "results"})

    assert load_backtest_config(tmp_path).strategy == "rsi_divergence"


def test_shape_errors_come_from_the_port(tmp_path) -> None:
    with pytest.raises(ValueError, match='"strategy" is required'):
        load_backtest_config(write_config(tmp_path, {"data": data(), "out": "o"}))


def test_errors_name_the_config_file(tmp_path) -> None:
    path = write_config(tmp_path, {"strategy": "nope", "data": data(), "out": "o"})

    with pytest.raises(ValueError, match=f"^{path}: "):
        load_backtest_config(path)


@pytest.mark.parametrize("config, message", [
    ({"strategy": "rsi_divergence", "data": data(format="mt5"), "out": "o"},
     '"data.format" is "mt5"; choose one of metatrader, dukascopy, clean-csv'),
    ({"strategy": "rsi_divergence", "data": data(symbol="EURUSX"), "out": "o"}, '"data.symbol"'),
    ({"strategy": "rsi_divergence", "data": data(timezone="New York"), "out": "o"}, '"data.timezone" is "New York"'),
    ({"strategy": "rsi_divergence", "data": data(timezone="../etc"), "out": "o"}, '"data.timezone" is "../etc"'),
    ({"strategy": "rsi_divergence", "data": data(timeframe="1min"), "out": "o"}, '"data.timeframe": invalid'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "timeframe": "5x"}, '"timeframe": invalid'),
    ({"strategy": "rsi_divergence", "data": data(timeframe="15m"), "out": "o"}, "not a whole multiple"),
    ({"strategy": "rsi_divergence", "data": data(timeframe="5m"), "out": "o", "timeframe": "7m"}, "not a whole multiple"),
    ({"strategy": "nope", "data": data(), "out": "o"}, '"strategy" is "nope"'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "ambiguity": "guess"}, '"ambiguity"'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "resolve_from": "later"}, '"resolve_from"'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "splits": "weekly"}, '"splits" is "weekly"'),
])
def test_rejects_invalid_values(tmp_path, config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_backtest_config(write_config(tmp_path, config))


def _with_parameters(tmp_path, strategy: str, parameters: dict):
    return load_backtest_config(write_config(tmp_path, {"strategy": strategy, "data": data(), "out": "o",
                                                        "strategy_parameters": parameters}))


def test_strategy_parameters_default_to_none_given(tmp_path) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": "rsi_divergence", "data": data(), "out": "o"}))

    assert config.strategy_parameters == {}


def test_strategy_parameters_are_converted_to_the_field_types(tmp_path) -> None:
    config = _with_parameters(tmp_path, "narrow_asia_fade",
                              {"study_end": "13:30", "rel_vol_min": 2, "rel_vol_length": 10})

    assert config.strategy_parameters == {"study_end": time(13, 30), "rel_vol_min": 2.0, "rel_vol_length": 10}
    assert isinstance(config.strategy_parameters["rel_vol_min"], float)


def test_strategy_parameters_build_the_strategy(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"risk_reward": 1.5})

    assert STRATEGIES[config.strategy](**config.strategy_parameters) == RsiDivergence(risk_reward=1.5)


def test_timezone_aware_times_take_a_zone_name(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"start_time": "08:00 Europe/London", "end_time": "16:30 broker"})

    assert config.strategy_parameters == {"start_time": time(8, 0, tzinfo=ZoneInfo("Europe/London")),
                                          "end_time": time(16, 30, tzinfo=BROKER_SERVER_TZ)}


def test_nullable_parameters_take_null(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"start_time": None, "end_time": "16:00 UTC"})

    assert config.strategy_parameters["start_time"] is None


@pytest.mark.parametrize("strategy, parameters, message", [
    ("rsi_divergence", {"start_time": "08:00"}, '"start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"start_time": "08:00 Mars/Olympus"}, '"start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"start_time": "08:00+01:00"}, '"start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"end_time": 8}, '"end_time" must be a time "HH:MM <zone>"'),
    ("narrow_asia_fade", {"study_end": "13:00 Europe/London"}, '"study_end" must be a time "HH:MM"'),
    ("narrow_asia_fade", {"study_end": None}, '"study_end" must be a time "HH:MM"'),
    ("rsi_divergence", {"risk_reward": None}, '"risk_reward" must be a number'),
    ("rsi_divergence", {"risk_reword": 1.5}, "has no parameter.*risk_reword.*its parameters: rsi_length"),
    ("rsi_divergence", {"rsi_length": 14.5}, '"rsi_length" must be a whole number'),
    ("rsi_divergence", {"risk_reward": "2"}, '"risk_reward" must be a number'),
    ("rsi_divergence", {"risk_reward": True}, '"risk_reward" must be a number'),
    ("narrow_asia_fade", {"study_end": "2pm"}, '"study_end" must be a time'),
    ("narrow_asia_fade", {"study_end": 14}, '"study_end" must be a time'),
    ("rsi_divergence", {"risk_reward": -1.0}, "invalid strategy_parameters.*risk_reward must be positive"),
])
def test_rejects_invalid_strategy_parameters(tmp_path, strategy: str, parameters: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _with_parameters(tmp_path, strategy, parameters)


@pytest.mark.parametrize("zone", ["broker", "Broker", "America/New_York", "UTC"])
def test_data_timezone_takes_broker_or_an_iana_name(tmp_path, zone: str) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": "rsi_divergence", "data": data(timezone=zone),
                                                          "out": "o"}))

    assert config.data.timezone == zone
