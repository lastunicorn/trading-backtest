"""Tests for `backtest.load_config`."""

import json
from datetime import time
from zoneinfo import ZoneInfo

import pytest

from domain.broker_clock import BROKER_SERVER_TZ
from backtest import BacktestConfig, CostConfig, DataConfig, load_config
from strategies import STRATEGIES
from strategies.rsi_divergence import RsiDivergence


def _data(source: str = "m5.csv", **extra) -> dict:
    return {"source": source, "format": "metatrader", "symbol": "EURUSD", **extra}


def _write(folder, config: dict, name: str = "backtest.json"):
    path = folder / name
    path.write_text(json.dumps(config))
    return path


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "narrow_asia_fade", "data": _data(), "out": "results"}))

    assert config == BacktestConfig(
        strategy="narrow_asia_fade",
        data=DataConfig(source=tmp_path / "m5.csv", format="metatrader", symbol="EURUSD", timeframe="1m",
                        timezone="UTC"),
        out=tmp_path / "results",
        timeframe="5m",
    )


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    _write(tmp_path, {"strategy": "rsi_divergence", "data": _data("m1"), "out": "results"})

    assert load_config(tmp_path).strategy == "rsi_divergence"


def test_paths_are_relative_to_the_config_file(tmp_path) -> None:
    folder = tmp_path / "runs" / "one"
    folder.mkdir(parents=True)
    config = load_config(_write(folder, {"strategy": "rsi_divergence", "data": _data("../../m1"), "out": "out"}))

    assert config.data.source == tmp_path / "m1"
    assert config.out == folder / "out"


def test_absolute_paths_are_kept(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "rsi_divergence", "data": _data("/data/m1"), "out": "/tmp/out"}))

    assert str(config.data.source) == "/data/m1"
    assert str(config.out) == "/tmp/out"


def test_reads_every_setting(tmp_path) -> None:
    config = load_config(_write(tmp_path, {
        "strategy": "rsi_divergence",
        "data": {"source": "duka", "format": "dukascopy", "symbol": "GBPUSD", "timeframe": "5m",
                 "timezone": "Etc/UTC"},
        "out": "out",
        "timeframe": "15m",
        "cost": {"spread": True, "commission_pips": 0.2},
        "ambiguity": "assume-sl",
        "resolve_from": "entry-bar",
        "splits": False,
    }))

    assert config == BacktestConfig(
        strategy="rsi_divergence", out=tmp_path / "out",
        data=DataConfig(source=tmp_path / "duka", format="dukascopy", symbol="GBPUSD", timeframe="5m",
                        timezone="Etc/UTC"),
        timeframe="15m",
        cost=CostConfig(spread=True, commission_pips=0.2), ambiguity="assume-sl",
        resolve_from="entry-bar", splits=False,
    )


def test_cost_keys_default_inside_the_cost_object(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "rsi_divergence", "data": _data(), "out": "o",
                                           "cost": {"commission_pips": 1}}))

    assert config.cost == CostConfig(spread=False, commission_pips=1.0)


@pytest.mark.parametrize("config, message", [
    ({"data": _data(), "out": "o"}, '"strategy" is required'),
    ({"strategy": "rsi_divergence", "data": _data()}, '"out" is required'),
    ({"strategy": "rsi_divergence", "out": "o"}, '"data" is required'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o"}, "unknown key.*source"),
    ({"strategy": "rsi_divergence", "data": "m5.csv", "out": "o"}, '"data" must be a JSON object'),
    ({"strategy": "rsi_divergence", "data": {"format": "metatrader", "symbol": "EURUSD"}, "out": "o"},
     '"data.source" is required'),
    ({"strategy": "rsi_divergence", "data": {"source": "m5.csv", "symbol": "EURUSD"}, "out": "o"},
     '"data.format" is required'),
    ({"strategy": "rsi_divergence", "data": {"source": "m5.csv", "format": "metatrader"}, "out": "o"},
     '"data.symbol" is required'),
    ({"strategy": "rsi_divergence", "data": _data(format="mt5"), "out": "o"},
     '"data.format" is "mt5"; choose one of metatrader, dukascopy, clean-csv'),
    ({"strategy": "rsi_divergence", "data": _data(format=5), "out": "o"}, '"data.format" must be a string'),
    ({"strategy": "rsi_divergence", "data": _data(symbol="EURUSX"), "out": "o"}, '"data.symbol"'),
    ({"strategy": "rsi_divergence", "data": _data(timezone="New York"), "out": "o"}, '"data.timezone" is "New York"'),
    ({"strategy": "rsi_divergence", "data": _data(timezone="../etc"), "out": "o"}, '"data.timezone" is "../etc"'),
    ({"strategy": "rsi_divergence", "data": _data(timezone=-5), "out": "o"}, '"data.timezone" must be a string'),
    ({"strategy": "rsi_divergence", "data": _data(dukascopy_years=[2024]), "out": "o"},
     "unknown key.*data.dukascopy_years"),
    ({"strategy": "rsi_divergence", "data": _data(timefrane="1m"), "out": "o"}, "unknown key.*data.timefrane"),
    ({"strategy": "rsi_divergence", "data": _data(timeframe=1), "out": "o"}, '"data.timeframe" must be a string'),
    ({"strategy": "rsi_divergence", "data": _data(timeframe="1min"), "out": "o"}, '"data.timeframe": invalid'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "timeframe": "5x"}, '"timeframe": invalid'),
    ({"strategy": "rsi_divergence", "data": _data(timeframe="15m"), "out": "o"}, "not a whole multiple"),
    ({"strategy": "rsi_divergence", "data": _data(timeframe="5m"), "out": "o", "timeframe": "7m"}, "not a whole multiple"),
    ({"strategy": "nope", "data": _data(), "out": "o"}, '"strategy" is "nope"'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "ambiguity": "guess"}, '"ambiguity"'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "resolve_from": "later"}, '"resolve_from"'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "symbol": "EURUSD"}, "unknown key"),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost_pip": 1.0}, "unknown key"),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "commission_pips": 0.2}, "unknown key.*commission_pips"),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": 1.7}, '"cost" must be a JSON object'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": {"commision_pips": 1.0}},
     "unknown key.*cost.commision_pips"),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": {"commission_pips": "1.7"}},
     '"cost.commission_pips" must be a number'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": {"commission_pips": True}},
     '"cost.commission_pips" must be a number'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": {"commission_pips": -0.5}},
     '"cost.commission_pips" cannot be negative'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "cost": {"spread": "yes"}},
     '"cost.spread" must be true or false'),
    ({"strategy": "rsi_divergence", "data": _data(), "out": "o", "splits": "no"}, '"splits" must be true or false'),
])
def test_rejects_an_invalid_config(tmp_path, config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        load_config(_write(tmp_path, config))


def test_rejects_malformed_json(tmp_path) -> None:
    (tmp_path / "backtest.json").write_text('{"strategy": ')

    with pytest.raises(ValueError, match="not valid JSON"):
        load_config(tmp_path)


def test_rejects_a_json_array(tmp_path) -> None:
    (tmp_path / "backtest.json").write_text("[]")

    with pytest.raises(ValueError, match="expected a JSON object"):
        load_config(tmp_path)


def _with_parameters(tmp_path, strategy: str, parameters: dict):
    return load_config(_write(tmp_path, {"strategy": strategy, "data": _data(), "out": "o",
                                         "strategy_parameters": parameters}))


def test_strategy_parameters_default_to_none_given(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "rsi_divergence", "data": _data(), "out": "o"}))

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


def test_strategy_parameters_must_be_an_object(tmp_path) -> None:
    with pytest.raises(ValueError, match='"strategy_parameters" must be a JSON object'):
        _with_parameters(tmp_path, "rsi_divergence", [1.5])


@pytest.mark.parametrize("zone", ["broker", "Broker", "America/New_York", "UTC"])
def test_data_timezone_takes_broker_or_an_iana_name(tmp_path, zone: str) -> None:
    config = load_config(_write(tmp_path, {"strategy": "rsi_divergence", "data": _data(timezone=zone), "out": "o"}))

    assert config.data.timezone == zone
