"""Read a backtest config -- a JSON file, or a folder holding `backtest.json` -- into a `BacktestConfig`.

    from ports.backtest_config_access import read_config

    config = read_config("backtests/narrow_asia_fade")   # the folder's backtest.json
    config.strategy, config.data.source, config.out, config.strategy_parameters

The file format is documented in help/backtest-framework/backtest-config.md.
This port checks the file's *shape* only: known keys, JSON types, required
keys. Relative `data.source` and `out` paths resolve against the config file's
own folder, not the working directory. Violations raise `ValueError` naming
the file, so a typo fails the run instead of silently falling back to a default.

Whether the values make sense -- a registered strategy, a known symbol or time
zone, strategy parameters of the right types -- is
`application.load_backtest_config_use_case`'s job; use `load_backtest_config`
there to get a fully validated config. Stdlib only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

CONFIG_FILE_NAME = "backtest.json"

Fail = Callable[[str], ValueError]


@dataclass(frozen=True)
class DataConfig:
    """The config's `data` object: where the bars come from and what they are.

    `source` is already resolved against the config file's folder. `format` is
    a `SourceFormat` value. `timeframe` is the bar size of the source as
    stored, not the one backtested on. `timezone` is the clock its timestamps
    are on, as `timezone_by_name` reads it ("broker" or an IANA name).
    """

    source: Path
    format: str
    symbol: str
    timeframe: str = "1m"
    timezone: str = "UTC"


@dataclass(frozen=True)
class CostConfig:
    """The config's `cost` object: what each trade pays, in pips.

    `commission_pips` is charged on every trade. With `spread`, each trade also
    pays the spread of the bar where it crosses to the ask; without it, the
    commission is the whole cost. The default is no cost at all.
    """

    spread: bool = False
    commission_pips: float = 0.0


@dataclass(frozen=True)
class BacktestConfig:
    """The settings of one CLI run, as written in its JSON config.

    Field names are the JSON keys. `out` is already resolved against the
    config file's folder. `timeframe` is the bar size to backtest on;
    `data.timeframe` divides it. The `ambiguity` and `resolve_from` defaults
    are the values of `AmbiguityPolicy.EXCLUDE` and `PositionCloseDelay.NEXT_BAR`;
    `splits` is a `SplitMode` value, default "none".

    `strategy_parameters` is the strategy's constructor arguments: raw JSON
    values from `read_config`, converted to the strategy's field types (a
    "HH:MM" string becomes a `datetime.time`) by `load_backtest_config`.
    """

    strategy: str
    data: DataConfig
    out: Path
    timeframe: str = "5m"
    cost: CostConfig = field(default_factory=CostConfig)
    ambiguity: str = "exclude"
    resolve_from: str = "next-bar"
    splits: str = "none"
    strategy_parameters: dict[str, object] = field(default_factory=dict)


# The JSON type each config key must have. bool is kept apart from the numbers
# on purpose: `"commission_pips": true` is a mistake, not 1 pip.
_CONFIG_KEY_TYPES = {
    "strategy": str,
    "data": dict,
    "out": str,
    "timeframe": str,
    "cost": dict,
    "ambiguity": str,
    "resolve_from": str,
    "splits": str,
    "strategy_parameters": dict,
}

_DATA_KEY_TYPES = {
    "source": str,
    "format": str,
    "symbol": str,
    "timeframe": str,
    "timezone": str,
}

_COST_KEY_TYPES = {
    "spread": bool,
    "commission_pips": float,
}


def find_config_file(path) -> Path:
    """`path` itself if it is a file, `path/backtest.json` if it is a folder."""
    path = Path(path)
    if path.is_dir():
        path = path / CONFIG_FILE_NAME
    if not path.is_file():
        raise FileNotFoundError(f"no backtest config at {path}")
    return path


def config_error(file: Path) -> Fail:
    """A factory for `ValueError`s about config `file`, each message prefixed with its path."""
    def fail(message: str) -> ValueError:
        return ValueError(f"{file}: {message}")
    return fail


def read_config(path) -> BacktestConfig:
    """Read a backtest config -- a JSON file, or a folder holding `backtest.json` -- checking its shape only.

    Unknown keys, wrong JSON types and missing required keys raise `ValueError`
    naming the file. The values themselves are not validated.
    """
    file = find_config_file(path)
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{file}: not valid JSON: {error}") from error
    if not isinstance(raw, dict):
        raise ValueError(f"{file}: expected a JSON object, got {type(raw).__name__}")

    fail = config_error(file)
    _check_keys(raw, _CONFIG_KEY_TYPES, "", fail)
    for key in ("strategy", "data", "out"):
        if key not in raw:
            raise fail(f'"{key}" is required')

    values = dict(raw)
    values["data"] = _data_config(file, raw["data"], fail)
    values["out"] = _relative_to(file, raw["out"])
    if "cost" in raw:
        values["cost"] = _cost_config(raw["cost"], fail)
    return BacktestConfig(**values)


def _data_config(file: Path, raw: dict, fail: Fail) -> DataConfig:
    """The `data` object, checked, with `source` resolved against the config file's folder."""
    _check_keys(raw, _DATA_KEY_TYPES, "data.", fail)
    for key in ("source", "format", "symbol"):
        if key not in raw:
            raise fail(f'"data.{key}" is required')

    values = dict(raw)
    values["source"] = _relative_to(file, raw["source"])
    return DataConfig(**values)


def _cost_config(raw: dict, fail: Fail) -> CostConfig:
    """The `cost` object, checked, with `commission_pips` as a float."""
    _check_keys(raw, _COST_KEY_TYPES, "cost.", fail)
    values = dict(raw)
    if "commission_pips" in raw:
        values["commission_pips"] = float(raw["commission_pips"])
        if values["commission_pips"] < 0:
            raise fail(f'"cost.commission_pips" cannot be negative, got {raw["commission_pips"]}')
    return CostConfig(**values)


def _relative_to(config_file: Path, path: str) -> Path:
    """`path` resolved against the config file's folder, with `..` folded away (symlinks untouched)."""
    return Path(os.path.normpath(config_file.parent / path))


_JSON_TYPE_NAMES = {str: "a string", float: "a number", int: "a whole number", bool: "true or false",
                    list: "a list", dict: "a JSON object"}


def json_type_name(expected: type) -> str:
    """How an error message names the JSON type that maps to `expected` ("a number" for float)."""
    return _JSON_TYPE_NAMES[expected]


def has_json_type(value, expected: type) -> bool:
    """Whether a parsed JSON `value` is of type `expected`: an int counts as a float, a bool as nothing else."""
    if isinstance(value, bool):
        return expected is bool
    if expected is float:
        return isinstance(value, (int, float))
    return isinstance(value, expected)


def _check_keys(raw: dict, key_types: dict[str, type], prefix: str, fail: Fail) -> None:
    """Reject keys not in `key_types` and values of the wrong JSON type; `prefix` names the nesting ("data.")."""
    unknown = sorted(set(raw) - set(key_types))
    if unknown:
        raise fail(f"unknown key(s) {', '.join(prefix + key for key in unknown)}; "
                   f"allowed: {', '.join(prefix + key for key in key_types)}")
    for key, value in raw.items():
        if not has_json_type(value, key_types[key]):
            raise fail(f'"{prefix}{key}" must be {json_type_name(key_types[key])}, got {json.dumps(value)}')
