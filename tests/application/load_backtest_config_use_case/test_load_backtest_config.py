"""Tests for `application.load_backtest_config_use_case.load_backtest_config`.

The shape checks (keys, JSON types, paths) are `read_config`'s and are tested
in tests/ports/backtest_config_access/backtest_config_reader/test_read_config.py.
"""

from datetime import time
from zoneinfo import ZoneInfo

import pytest

from application.load_backtest_config_use_case import load_backtest_config
from domain.market_data.broker_clock import BROKER_SERVER_TZ
from domain.market_data.trading_session import LONDON_SESSION
from ports.backtest_config_access import BacktestConfig, DataSourceConfig, SimulationConfig, StrategyConfig
from strategies import STRATEGIES
from strategies.rsi_divergence import RsiDivergence
from tests.ports.backtest_config_access.backtest_config_reader._fakes import data_source, write_config


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": {"name": "narrow_asia_fade"},
                                                          "data_source": data_source(), "out": "results"}))

    assert config == BacktestConfig(
        strategy=StrategyConfig(name="narrow_asia_fade"),
        data_source=DataSourceConfig(path=tmp_path / "m5.csv", format="metatrader", symbol="EURUSD", timeframe="1m",
                                     timezone="UTC"),
        out=tmp_path / "results",
        simulation=SimulationConfig(timeframe="5m"),
    )


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    write_config(tmp_path, {"strategy": {"name": "rsi_divergence"}, "data_source": data_source("m1"), "out": "results"})

    assert load_backtest_config(tmp_path).strategy.name == "rsi_divergence"


def test_shape_errors_come_from_the_port(tmp_path) -> None:
    with pytest.raises(ValueError, match='"strategy" is required'):
        load_backtest_config(write_config(tmp_path, {"data_source": data_source(), "out": "o"}))


def test_errors_name_the_config_file(tmp_path) -> None:
    path = write_config(tmp_path, {"strategy": {"name": "nope"}, "data_source": data_source(), "out": "o"})

    with pytest.raises(ValueError, match=f"^{path}: "):
        load_backtest_config(path)


@pytest.mark.parametrize("config, message", [
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(format="mt5"), "out": "o"},
     '"data_source.format" is "mt5"; choose one of metatrader, histdata, dukascopy'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(symbol="EURUSX"), "out": "o"},
     '"data_source.symbol"'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timezone="New York"), "out": "o"},
     '"data_source.timezone" is "New York"'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timezone="../etc"), "out": "o"},
     '"data_source.timezone" is "../etc"'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timeframe="1min"), "out": "o"},
     '"data_source.timeframe": invalid'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"timeframe": "5x"}},
     '"simulation.timeframe": invalid'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timeframe="15m"), "out": "o"},
     "not a whole multiple"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timeframe="5m"), "out": "o",
      "simulation": {"timeframe": "7m"}},
     '"simulation.timeframe" 7m is not a whole multiple'),
    ({"strategy": {"name": "nope"}, "data_source": data_source(), "out": "o"}, '"strategy.name" is "nope"'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"ambiguity": "guess"}},
     '"simulation.ambiguity" is "guess"'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "splits": "weekly"},
     '"splits" is "weekly"'),
])
def test_rejects_invalid_values(tmp_path, config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_backtest_config(write_config(tmp_path, config))


def _with_parameters(tmp_path, strategy: str, parameters: dict):
    return load_backtest_config(write_config(tmp_path, {"strategy": {"name": strategy, "parameters": parameters},
                                                        "data_source": data_source(), "out": "o"}))


def test_strategy_parameters_default_to_none_given(tmp_path) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"},
                                                          "data_source": data_source(), "out": "o"}))

    assert config.strategy.parameters == {}


def test_strategy_parameters_are_converted_to_the_field_types(tmp_path) -> None:
    config = _with_parameters(tmp_path, "narrow_asia_fade",
                              {"study_end": "13:30", "rel_vol_min": 2, "rel_vol_length": 10})

    assert config.strategy.parameters == {"study_end": time(13, 30), "rel_vol_min": 2.0, "rel_vol_length": 10}
    assert isinstance(config.strategy.parameters["rel_vol_min"], float)


def test_strategy_parameters_build_the_strategy(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"risk_reward": 1.5})

    assert STRATEGIES[config.strategy.name](**config.strategy.parameters) == RsiDivergence(risk_reward=1.5)


def test_timezone_aware_times_take_a_zone_name(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"start_time": "08:00 Europe/London",
                                                           "end_time": "16:30 broker"})

    assert config.strategy.parameters == {"start_time": time(8, 0, tzinfo=ZoneInfo("Europe/London")),
                                          "end_time": time(16, 30, tzinfo=BROKER_SERVER_TZ)}


def test_trading_sessions_take_a_sessions_name(tmp_path) -> None:
    config = _with_parameters(tmp_path, "orb_break_entry", {"session": "London"})

    assert config.strategy.parameters == {"session": LONDON_SESSION}


def test_nullable_parameters_take_null(tmp_path) -> None:
    config = _with_parameters(tmp_path, "rsi_divergence", {"start_time": None, "end_time": "16:00 UTC"})

    assert config.strategy.parameters["start_time"] is None


@pytest.mark.parametrize("strategy, parameters, message", [
    ("rsi_divergence", {"start_time": "08:00"}, '"strategy.parameters.start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"start_time": "08:00 Mars/Olympus"},
     '"strategy.parameters.start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"start_time": "08:00+01:00"}, '"strategy.parameters.start_time" must be a time "HH:MM <zone>"'),
    ("rsi_divergence", {"end_time": 8}, '"strategy.parameters.end_time" must be a time "HH:MM <zone>"'),
    ("narrow_asia_fade", {"study_end": "13:00 Europe/London"},
     '"strategy.parameters.study_end" must be a time "HH:MM"'),
    ("narrow_asia_fade", {"study_end": None}, '"strategy.parameters.study_end" must be a time "HH:MM"'),
    ("rsi_divergence", {"risk_reward": None}, '"strategy.parameters.risk_reward" must be a number'),
    ("rsi_divergence", {"risk_reword": 1.5}, "has no parameter.*risk_reword.*its parameters: rsi_length"),
    ("rsi_divergence", {"rsi_length": 14.5}, '"strategy.parameters.rsi_length" must be a whole number'),
    ("rsi_divergence", {"risk_reward": "2"}, '"strategy.parameters.risk_reward" must be a number'),
    ("rsi_divergence", {"risk_reward": True}, '"strategy.parameters.risk_reward" must be a number'),
    ("narrow_asia_fade", {"study_end": "2pm"}, '"strategy.parameters.study_end" must be a time'),
    ("narrow_asia_fade", {"study_end": 14}, '"strategy.parameters.study_end" must be a time'),
    ("rsi_divergence", {"risk_reward": -1.0}, 'invalid "strategy.parameters".*risk_reward must be positive'),
    ("orb_break_entry", {"session": "Frankfurt"},
     '"strategy.parameters.session" is "Frankfurt"; choose one of Tokyo, Asia, London, New York'),
    ("orb_break_entry", {"session": None}, '"strategy.parameters.session" is null; choose one of'),
])
def test_rejects_invalid_strategy_parameters(tmp_path, strategy: str, parameters: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _with_parameters(tmp_path, strategy, parameters)


@pytest.mark.parametrize("zone", ["broker", "Broker", "histdata", "America/New_York", "UTC"])
def test_data_source_timezone_takes_broker_histdata_or_an_iana_name(tmp_path, zone: str) -> None:
    config = load_backtest_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"},
                                                          "data_source": data_source(timezone=zone), "out": "o"}))

    assert config.data_source.timezone == zone
