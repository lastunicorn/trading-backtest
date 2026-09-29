"""Reads the JSON config that drives one `backtest.py` run, checking its shape only.

Re-exported so callers can use the short form:

    from ports.backtest_config_access import read_config, BacktestConfig

For a config whose values are validated too, use
`application.load_backtest_config_use_case.load_backtest_config`.
"""

from ports.backtest_config_access.backtest_config_reader import (
    CONFIG_FILE_NAME,
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

__all__ = [
    "CONFIG_FILE_NAME",
    "BacktestConfig",
    "CostConfig",
    "DataConfig",
    "Fail",
    "config_error",
    "find_config_file",
    "has_json_type",
    "json_type_name",
    "read_config",
]
