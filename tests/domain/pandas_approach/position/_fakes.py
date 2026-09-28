"""Shared builders for the `domain.pandas_approach.position` tests."""

import pandas as pd

from domain.pandas_approach.position import Position, Side

T0 = pd.Timestamp("2026-01-05 10:00")


def long_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.LONG, sl=1.0980, tp=1.1040)
    fields.update(overrides)
    return Position(**fields)


def short_position(**overrides) -> Position:
    fields = dict(open_dt=T0, open_price=1.1000, side=Side.SHORT, sl=1.1020, tp=1.0960)
    fields.update(overrides)
    return Position(**fields)
