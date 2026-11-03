"""Tests for `ports.backtest_config_access.backtest_config_reader.read_config`."""

import pytest

from ports.backtest_config_access import (
    BacktestConfig,
    CostConfig,
    DataSourceConfig,
    SimulationConfig,
    StrategyConfig,
    read_config,
)
from tests.ports.backtest_config_access.backtest_config_reader._fakes import data_source, write_config


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "narrow_asia_fade"}, "data_source": data_source(),
                                                 "out": "results"}))

    assert config == BacktestConfig(
        strategy=StrategyConfig(name="narrow_asia_fade", parameters={}),
        data_source=DataSourceConfig(path=tmp_path / "m5.csv", format="metatrader", symbol="EURUSD", timeframe="1m",
                                     timezone="UTC"),
        out=tmp_path / "results",
        simulation=SimulationConfig(timeframe="5m", ambiguity="exclude", resolve_from="next-bar",
                                    cost=CostConfig(spread=False, commission_pips=0.0)),
        splits="none",
    )


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    write_config(tmp_path, {"strategy": {"name": "rsi_divergence"}, "data_source": data_source("m1"), "out": "results"})

    assert read_config(tmp_path).strategy.name == "rsi_divergence"


def test_paths_are_relative_to_the_config_file(tmp_path) -> None:
    folder = tmp_path / "runs" / "one"
    folder.mkdir(parents=True)
    config = read_config(write_config(folder, {"strategy": {"name": "rsi_divergence"},
                                               "data_source": data_source("../../m1"),
                                               "out": "out"}))

    assert config.data_source.path == tmp_path / "m1"
    assert config.out == folder / "out"


def test_absolute_paths_are_kept(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"},
                                                 "data_source": data_source("/data/m1"),
                                                 "out": "/tmp/out"}))

    assert str(config.data_source.path) == "/data/m1"
    assert str(config.out) == "/tmp/out"


def test_reads_every_setting(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {
        "strategy": {"name": "rsi_divergence", "parameters": {"risk_reward": 1.5}},
        "data_source": {"path": "duka", "format": "dukascopy", "symbol": "GBPUSD", "timeframe": "5m",
                        "timezone": "Etc/UTC"},
        "out": "out",
        "simulation": {
            "timeframe": "15m",
            "ambiguity": "assume-sl",
            "resolve_from": "entry-bar",
            "cost": {"spread": True, "commission_pips": 0.2},
        },
        "splits": "monthly",
    }))

    assert config == BacktestConfig(
        strategy=StrategyConfig(name="rsi_divergence", parameters={"risk_reward": 1.5}), out=tmp_path / "out",
        data_source=DataSourceConfig(path=tmp_path / "duka", format="dukascopy", symbol="GBPUSD", timeframe="5m",
                                     timezone="Etc/UTC"),
        simulation=SimulationConfig(timeframe="15m", ambiguity="assume-sl", resolve_from="entry-bar",
                                    cost=CostConfig(spread=True, commission_pips=0.2)),
        splits="monthly",
    )


def test_simulation_keys_default_inside_the_simulation_object(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"}, "data_source": data_source(),
                                                 "out": "o",
                                                 "simulation": {"resolve_from": "entry-bar"}}))

    assert config.simulation == SimulationConfig(resolve_from="entry-bar")


def test_cost_keys_default_inside_the_cost_object(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"}, "data_source": data_source(),
                                                 "out": "o",
                                                 "simulation": {"cost": {"commission_pips": 1}}}))

    assert config.simulation.cost == CostConfig(spread=False, commission_pips=1.0)
    assert isinstance(config.simulation.cost.commission_pips, float)


def test_strategy_parameters_default_to_none(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "rsi_divergence"}, "data_source": data_source(),
                                                 "out": "o"}))

    assert config.strategy == StrategyConfig(name="rsi_divergence", parameters={})


def test_strategy_parameters_are_kept_as_json_values(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {
        "strategy": {"name": "narrow_asia_fade", "parameters": {"study_end": "13:30", "rel_vol_min": 2}},
        "data_source": data_source(), "out": "o"}))

    assert config.strategy.parameters == {"study_end": "13:30", "rel_vol_min": 2}


def test_values_are_not_validated(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": {"name": "nope"},
                                                 "data_source": data_source(symbol="EURUSX", timezone="Mars"),
                                                 "out": "o", "simulation": {"ambiguity": "guess"}}))

    assert (config.strategy.name, config.data_source.symbol, config.data_source.timezone,
            config.simulation.ambiguity) == \
           ("nope", "EURUSX", "Mars", "guess")


@pytest.mark.parametrize("config, message", [
    ({"data_source": data_source(), "out": "o"}, '"strategy" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source()}, '"out" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "out": "o"}, '"data_source" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "source": "m5.csv", "out": "o"}, "unknown key.*source"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": "m5.csv", "out": "o"},
     '"data_source" must be a JSON object'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": {"format": "metatrader", "symbol": "EURUSD"}, "out": "o"},
     '"data_source.path" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": {"path": "m5.csv", "symbol": "EURUSD"}, "out": "o"},
     '"data_source.format" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": {"path": "m5.csv", "format": "metatrader"}, "out": "o"},
     '"data_source.symbol" is required'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(format=5), "out": "o"},
     '"data_source.format" must be a string'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timezone=-5), "out": "o"},
     '"data_source.timezone" must be a string'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(dukascopy_years=[2024]), "out": "o"},
     "unknown key.*data_source.dukascopy_years"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timefrane="1m"), "out": "o"},
     "unknown key.*data_source.timefrane"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(timeframe=1), "out": "o"},
     '"data_source.timeframe" must be a string'),
    ({"strategy": {"name": "rsi_divergence"}, "data": data_source(), "out": "o"}, "unknown key.*data;"),
    ({"strategy": {"name": "rsi_divergence"},
      "data_source": {"source": "m5.csv", "format": "metatrader", "symbol": "EURUSD"}, "out": "o"},
     "unknown key.*data_source.source"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "symbol": "EURUSD"},
     "unknown key"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "cost_pip": 1.0},
     "unknown key"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "commission_pips": 0.2},
     "unknown key.*commission_pips"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "timeframe": "5m"},
     "unknown key.*timeframe"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "ambiguity": "exclude"},
     "unknown key.*ambiguity"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "resolve_from": "entry-bar"},
     "unknown key.*resolve_from"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "cost": {}},
     "unknown key.*cost"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "simulation": "5m"},
     '"simulation" must be a JSON object'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"splits": "dvt"}},
     "unknown key.*simulation.splits"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "simulation": {"timeframe": 5}},
     '"simulation.timeframe" must be a string'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "simulation": {"cost": 1.7}},
     '"simulation.cost" must be a JSON object'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"cost": {"commision_pips": 1.0}}},
     "unknown key.*simulation.cost.commision_pips"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"cost": {"commission_pips": "1.7"}}},
     '"simulation.cost.commission_pips" must be a number'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"cost": {"commission_pips": True}}},
     '"simulation.cost.commission_pips" must be a number'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"cost": {"commission_pips": -0.5}}},
     '"simulation.cost.commission_pips" cannot be negative'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o",
      "simulation": {"cost": {"spread": "yes"}}},
     '"simulation.cost.spread" must be true or false'),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "splits": True},
     '"splits" must be a string'),
    ({"strategy": "rsi_divergence", "data_source": data_source(), "out": "o"}, '"strategy" must be a JSON object'),
    ({"strategy": {}, "data_source": data_source(), "out": "o"}, '"strategy.name" is required'),
    ({"strategy": {"name": 5}, "data_source": data_source(), "out": "o"}, '"strategy.name" must be a string'),
    ({"strategy": {"name": "rsi_divergence", "parameters": [1.5]}, "data_source": data_source(), "out": "o"},
     '"strategy.parameters" must be a JSON object'),
    ({"strategy": {"name": "rsi_divergence", "params": {}}, "data_source": data_source(), "out": "o"},
     "unknown key.*strategy.params"),
    ({"strategy": {"name": "rsi_divergence"}, "data_source": data_source(), "out": "o", "strategy_parameters": {}},
     "unknown key.*strategy_parameters"),
])
def test_rejects_a_config_of_the_wrong_shape(tmp_path, config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_config(write_config(tmp_path, config))


def test_errors_name_the_config_file(tmp_path) -> None:
    path = write_config(tmp_path, {"data_source": data_source(), "out": "o"})

    with pytest.raises(ValueError, match=f"^{path}: "):
        read_config(path)


def test_rejects_malformed_json(tmp_path) -> None:
    (tmp_path / "backtest.json").write_text('{"strategy": ')

    with pytest.raises(ValueError, match="not valid JSON"):
        read_config(tmp_path)


def test_rejects_a_json_array(tmp_path) -> None:
    (tmp_path / "backtest.json").write_text("[]")

    with pytest.raises(ValueError, match="expected a JSON object"):
        read_config(tmp_path)


def test_a_missing_file_raises_file_not_found(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_config(tmp_path)
