"""Builders for backtest config files on disk."""

import json


def data(source: str = "m5.csv", **extra) -> dict:
    """A valid `data` object, with `extra` keys added or overridden."""
    return {"source": source, "format": "metatrader", "symbol": "EURUSD", **extra}


def write_config(folder, config: dict, name: str = "backtest.json"):
    """`config` written as JSON to `folder/name`; returns the file's path."""
    path = folder / name
    path.write_text(json.dumps(config))
    return path
