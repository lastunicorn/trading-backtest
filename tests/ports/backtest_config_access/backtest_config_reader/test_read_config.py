"""Tests for `ports.backtest_config_access.backtest_config_reader.read_config`."""

import pytest

from ports.backtest_config_access import BacktestConfig, CostConfig, DataConfig, read_config
from tests.ports.backtest_config_access.backtest_config_reader._fakes import data, write_config


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": "narrow_asia_fade", "data": data(), "out": "results"}))

    assert config == BacktestConfig(
        strategy="narrow_asia_fade",
        data=DataConfig(source=tmp_path / "m5.csv", format="metatrader", symbol="EURUSD", timeframe="1m",
                        timezone="UTC"),
        out=tmp_path / "results",
        timeframe="5m",
        cost=CostConfig(spread=False, commission_pips=0.0),
        ambiguity="exclude",
        resolve_from="next-bar",
        splits=True,
        strategy_parameters={},
    )


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    write_config(tmp_path, {"strategy": "rsi_divergence", "data": data("m1"), "out": "results"})

    assert read_config(tmp_path).strategy == "rsi_divergence"


def test_paths_are_relative_to_the_config_file(tmp_path) -> None:
    folder = tmp_path / "runs" / "one"
    folder.mkdir(parents=True)
    config = read_config(write_config(folder, {"strategy": "rsi_divergence", "data": data("../../m1"), "out": "out"}))

    assert config.data.source == tmp_path / "m1"
    assert config.out == folder / "out"


def test_absolute_paths_are_kept(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": "rsi_divergence", "data": data("/data/m1"),
                                                 "out": "/tmp/out"}))

    assert str(config.data.source) == "/data/m1"
    assert str(config.out) == "/tmp/out"


def test_reads_every_setting(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {
        "strategy": "rsi_divergence",
        "data": {"source": "duka", "format": "dukascopy", "symbol": "GBPUSD", "timeframe": "5m",
                 "timezone": "Etc/UTC"},
        "out": "out",
        "timeframe": "15m",
        "cost": {"spread": True, "commission_pips": 0.2},
        "ambiguity": "assume-sl",
        "resolve_from": "entry-bar",
        "splits": False,
        "strategy_parameters": {"risk_reward": 1.5},
    }))

    assert config == BacktestConfig(
        strategy="rsi_divergence", out=tmp_path / "out",
        data=DataConfig(source=tmp_path / "duka", format="dukascopy", symbol="GBPUSD", timeframe="5m",
                        timezone="Etc/UTC"),
        timeframe="15m",
        cost=CostConfig(spread=True, commission_pips=0.2), ambiguity="assume-sl",
        resolve_from="entry-bar", splits=False, strategy_parameters={"risk_reward": 1.5},
    )


def test_cost_keys_default_inside_the_cost_object(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": "rsi_divergence", "data": data(), "out": "o",
                                                 "cost": {"commission_pips": 1}}))

    assert config.cost == CostConfig(spread=False, commission_pips=1.0)
    assert isinstance(config.cost.commission_pips, float)


def test_strategy_parameters_are_kept_as_json_values(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": "narrow_asia_fade", "data": data(), "out": "o",
                                                 "strategy_parameters": {"study_end": "13:30", "rel_vol_min": 2}}))

    assert config.strategy_parameters == {"study_end": "13:30", "rel_vol_min": 2}


def test_values_are_not_validated(tmp_path) -> None:
    config = read_config(write_config(tmp_path, {"strategy": "nope", "data": data(symbol="EURUSX", timezone="Mars"),
                                                 "out": "o", "ambiguity": "guess"}))

    assert (config.strategy, config.data.symbol, config.data.timezone, config.ambiguity) == \
           ("nope", "EURUSX", "Mars", "guess")


@pytest.mark.parametrize("config, message", [
    ({"data": data(), "out": "o"}, '"strategy" is required'),
    ({"strategy": "rsi_divergence", "data": data()}, '"out" is required'),
    ({"strategy": "rsi_divergence", "out": "o"}, '"data" is required'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o"}, "unknown key.*source"),
    ({"strategy": "rsi_divergence", "data": "m5.csv", "out": "o"}, '"data" must be a JSON object'),
    ({"strategy": "rsi_divergence", "data": {"format": "metatrader", "symbol": "EURUSD"}, "out": "o"},
     '"data.source" is required'),
    ({"strategy": "rsi_divergence", "data": {"source": "m5.csv", "symbol": "EURUSD"}, "out": "o"},
     '"data.format" is required'),
    ({"strategy": "rsi_divergence", "data": {"source": "m5.csv", "format": "metatrader"}, "out": "o"},
     '"data.symbol" is required'),
    ({"strategy": "rsi_divergence", "data": data(format=5), "out": "o"}, '"data.format" must be a string'),
    ({"strategy": "rsi_divergence", "data": data(timezone=-5), "out": "o"}, '"data.timezone" must be a string'),
    ({"strategy": "rsi_divergence", "data": data(dukascopy_years=[2024]), "out": "o"},
     "unknown key.*data.dukascopy_years"),
    ({"strategy": "rsi_divergence", "data": data(timefrane="1m"), "out": "o"}, "unknown key.*data.timefrane"),
    ({"strategy": "rsi_divergence", "data": data(timeframe=1), "out": "o"}, '"data.timeframe" must be a string'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "symbol": "EURUSD"}, "unknown key"),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost_pip": 1.0}, "unknown key"),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "commission_pips": 0.2}, "unknown key.*commission_pips"),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": 1.7}, '"cost" must be a JSON object'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": {"commision_pips": 1.0}},
     "unknown key.*cost.commision_pips"),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": {"commission_pips": "1.7"}},
     '"cost.commission_pips" must be a number'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": {"commission_pips": True}},
     '"cost.commission_pips" must be a number'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": {"commission_pips": -0.5}},
     '"cost.commission_pips" cannot be negative'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "cost": {"spread": "yes"}},
     '"cost.spread" must be true or false'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "splits": "no"}, '"splits" must be true or false'),
    ({"strategy": "rsi_divergence", "data": data(), "out": "o", "strategy_parameters": [1.5]},
     '"strategy_parameters" must be a JSON object'),
])
def test_rejects_a_config_of_the_wrong_shape(tmp_path, config: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        read_config(write_config(tmp_path, config))


def test_errors_name_the_config_file(tmp_path) -> None:
    path = write_config(tmp_path, {"data": data(), "out": "o"})

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
