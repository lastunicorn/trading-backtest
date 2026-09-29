"""Load a backtest config and check that its values fit what a backtest can run.

    from application.load_backtest_config_use_case import cost_model, load_backtest_config

    config = load_backtest_config("backtests/narrow_asia_fade")   # the folder's backtest.json
    STRATEGIES[config.strategy](**config.strategy_parameters)     # already the strategy's field types
    cost_model(config.cost)                                        # the CostModel the config describes

`ports.backtest_config_access.read_config` reads the file and checks its
shape; this adds what needs the rest of the code base to decide: the strategy
is registered and its parameters convert to its field types (and build it),
the source format, symbol and time zone exist, the timeframes fit together,
and `ambiguity`/`resolve_from` name a policy. Every failure is a `ValueError`
naming the config file.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from dataclasses import fields, is_dataclass
from datetime import time as clock_time
from zoneinfo import ZoneInfoNotFoundError

from application.load_historical_data_use_case import SourceFormat
from domain.broker_clock import timezone_by_name
from domain.pandas_approach.backtest import AmbiguityPolicy, PositionCloseDelay
from domain.pandas_approach.cost_model import CostModel, FixedCost, SpreadCost
from domain.sample_size import SampleSize
from domain.symbol import by_ticker
from domain.time_window import ZonedTime
from ports.backtest_config_access import (
    BacktestConfig,
    CostConfig,
    DataConfig,
    Fail,
    config_error,
    find_config_file,
    has_json_type,
    json_type_name,
    read_config,
)
from strategies import STRATEGIES


def load_backtest_config(path) -> BacktestConfig:
    """Read and validate a backtest config: a JSON file, or a folder holding `backtest.json`.

    Unknown keys, wrong types and invalid choices raise `ValueError` naming the
    file, so a typo fails the run instead of silently falling back to a default.
    """
    file = find_config_file(path)
    config = read_config(file)
    fail = config_error(file)

    _check_choice(config.strategy, "strategy", sorted(STRATEGIES), fail)
    _check_choice(config.ambiguity, "ambiguity", [policy.value for policy in AmbiguityPolicy], fail)
    _check_choice(config.resolve_from, "resolve_from", [delay.value for delay in PositionCloseDelay], fail)
    _check_data(config.data, fail)

    timeframe = _parse_timeframe(config.timeframe, "timeframe", fail)
    if not timeframe.can_be_resampled_from(_parse_timeframe(config.data.timeframe, "data.timeframe", fail)):
        raise fail(f'"timeframe" {timeframe} is not a whole multiple of the source\'s '
                   f'"data.timeframe" {config.data.timeframe}; resampling only coarsens')

    return dataclasses.replace(
        config, strategy_parameters=_strategy_parameters(config.strategy, config.strategy_parameters, fail))


def cost_model(cost: CostConfig) -> CostModel:
    """The `CostModel` a config's `cost` object describes: `SpreadCost` with `spread`, else `FixedCost`."""
    if cost.spread:
        return SpreadCost(commission_pips=cost.commission_pips)
    return FixedCost(pips=cost.commission_pips)


def _check_data(data: DataConfig, fail: Fail) -> None:
    """The `data` object's format, symbol and time zone name things that exist."""
    _check_choice(data.format, "data.format", [source_format.value for source_format in SourceFormat], fail)
    try:
        by_ticker(data.symbol)
    except ValueError as error:
        raise fail(f'"data.symbol": {error}') from error
    try:
        timezone_by_name(data.timezone)
    except (KeyError, ValueError) as error:  # ZoneInfoNotFoundError is a KeyError
        raise fail(f'"data.timezone" is {json.dumps(data.timezone)}: not "broker" or an IANA time zone '
                   f'name such as "UTC" or "America/New_York"') from error


def _parse_timeframe(value: str, key: str, fail: Fail) -> SampleSize:
    try:
        return SampleSize.Parse(value)
    except ValueError as error:
        raise fail(f'"{key}": {error}') from error


def _strategy_parameters(name: str, raw: dict, fail: Fail) -> dict[str, object]:
    """`raw` converted to the field types of strategy `name`, checked by building the strategy once.

    Building it here means an out-of-range value (rejected by the strategy's
    `__post_init__`) fails before any data is loaded, not after.
    """
    strategy_class = STRATEGIES[name]
    types = typing.get_type_hints(strategy_class, include_extras=True)
    names = [f.name for f in fields(strategy_class) if f.init] if is_dataclass(strategy_class) else []

    unknown = sorted(set(raw) - set(names))
    if unknown:
        raise fail(f"{name} has no parameter(s) {', '.join(unknown)}; "
                   f"its parameters: {', '.join(names) or 'none'}")

    converted = {key: _strategy_parameter(key, value, types[key], fail) for key, value in raw.items()}

    try:
        strategy_class(**converted)
    except (TypeError, ValueError) as error:
        raise fail(f"invalid strategy_parameters for {name}: {error}") from error
    return converted


def _strategy_parameter(key: str, value, expected, fail: Fail):
    """One strategy parameter converted to its field's type `expected`; a `X | None` field also takes null."""
    arguments = [a for a in typing.get_args(expected) if a is not type(None)]
    if typing.get_origin(expected) in (typing.Union, types.UnionType) and len(arguments) == 1:
        if value is None:
            return None
        expected = arguments[0]

    if expected == ZonedTime:
        return _parse_time(key, value, zoned=True, fail=fail)
    if expected is clock_time:
        return _parse_time(key, value, zoned=False, fail=fail)
    if expected in (int, float, bool, str):
        if not has_json_type(value, expected):
            raise fail(f'strategy parameter "{key}" must be {json_type_name(expected)}, got {json.dumps(value)}')
        return float(value) if expected is float else value
    raise fail(f'strategy parameter "{key}" has type {expected}, which a JSON config cannot set')


def _parse_time(key: str, value, *, zoned: bool, fail: Fail) -> clock_time:
    """ "HH:MM" -> a naive time on the data's clock; with `zoned`, "HH:MM <zone>" -> a timezone-aware one.

    The zone is anything `timezone_by_name` reads: "broker" or an IANA name.
    """
    form = '"HH:MM <zone>" (e.g. "08:00 Europe/London" or "10:00 broker")' if zoned else '"HH:MM"'
    parts = value.split() if isinstance(value, str) else []
    try:
        if len(parts) != (2 if zoned else 1):
            raise ValueError
        parsed = clock_time.fromisoformat(parts[0])
        if parsed.tzinfo is not None:
            raise ValueError
        return parsed.replace(tzinfo=timezone_by_name(parts[1])) if zoned else parsed
    except (ValueError, ZoneInfoNotFoundError):
        raise fail(f'strategy parameter "{key}" must be a time {form}, got {json.dumps(value)}') from None


def _check_choice(value: str, key: str, choices: list[str], fail: Fail) -> None:
    if value not in choices:
        raise fail(f'"{key}" is {json.dumps(value)}; choose one of {", ".join(choices)}')
