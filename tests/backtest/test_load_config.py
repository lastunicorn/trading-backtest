"""Tests for `backtest.load_config`."""

import json

import pytest

from backtest import BacktestConfig, load_config


def _write(folder, config: dict, name: str = "backtest.json"):
    path = folder / name
    path.write_text(json.dumps(config))
    return path


def test_minimal_config_takes_the_defaults(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "narrow_asia_fade", "source": "m5.csv", "out": "results"}))

    assert config == BacktestConfig(strategy="narrow_asia_fade", source=tmp_path / "m5.csv", out=tmp_path / "results")


def test_reads_backtest_json_from_a_folder(tmp_path) -> None:
    _write(tmp_path, {"strategy": "rsi_divergence", "source": "m1", "out": "results"})

    assert load_config(tmp_path).strategy == "rsi_divergence"


def test_paths_are_relative_to_the_config_file(tmp_path) -> None:
    folder = tmp_path / "runs" / "one"
    folder.mkdir(parents=True)
    config = load_config(_write(folder, {"strategy": "rsi_divergence", "source": "../../m1", "out": "out"}))

    assert config.source == tmp_path / "m1"
    assert config.out == folder / "out"


def test_absolute_paths_are_kept(tmp_path) -> None:
    config = load_config(_write(tmp_path, {"strategy": "rsi_divergence", "source": "/data/m1", "out": "/tmp/out"}))

    assert str(config.source) == "/data/m1"
    assert str(config.out) == "/tmp/out"


def test_reads_every_setting(tmp_path) -> None:
    config = load_config(_write(tmp_path, {
        "strategy": "rsi_divergence",
        "dukascopy_years": [2024, 2025],
        "out": "out",
        "timeframe": "15m",
        "symbol": "GBPUSD",
        "cost_pips": 2,
        "spread_cost": True,
        "commission_pips": 0.2,
        "ambiguity": "assume-sl",
        "resolve_from": "entry-bar",
        "splits": False,
    }))

    assert config == BacktestConfig(
        strategy="rsi_divergence", out=tmp_path / "out", dukascopy_years=(2024, 2025), timeframe="15m",
        symbol="GBPUSD", cost_pips=2.0, spread_cost=True, commission_pips=0.2, ambiguity="assume-sl",
        resolve_from="entry-bar", splits=False,
    )


@pytest.mark.parametrize("config, message", [
    ({"source": "m5.csv", "out": "o"}, '"strategy" is required'),
    ({"strategy": "rsi_divergence", "source": "m5.csv"}, '"out" is required'),
    ({"strategy": "rsi_divergence", "out": "o"}, "exactly one of"),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "dukascopy_years": [2024], "out": "o"}, "exactly one of"),
    ({"strategy": "nope", "source": "m5.csv", "out": "o"}, '"strategy" is "nope"'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "ambiguity": "guess"}, '"ambiguity"'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "resolve_from": "later"}, '"resolve_from"'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "cost_pip": 1.0}, "unknown key"),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "cost_pips": "1.7"}, '"cost_pips" must be'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "cost_pips": True}, '"cost_pips" must be'),
    ({"strategy": "rsi_divergence", "source": "m5.csv", "out": "o", "splits": "no"}, '"splits" must be'),
    ({"strategy": "rsi_divergence", "dukascopy_years": [], "out": "o"}, '"dukascopy_years"'),
    ({"strategy": "rsi_divergence", "dukascopy_years": ["2024"], "out": "o"}, '"dukascopy_years"'),
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
