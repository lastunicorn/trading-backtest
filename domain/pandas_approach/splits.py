"""The chronological discovery / validation / test split.

    from domain.pandas_approach.splits import Split, assign_splits, split_dates

    by_date = split_dates(data.data["datetime"].dt.date)       # {date: Split}
    trades["split"] = assign_splits(trades["open_dt"], by_date)

The research methodology's invariant: calendar days are sorted and sliced
60 / 20 / 20, never shuffled, and a result only counts when it holds in all
three. The slicing is v28's `split_dates` exactly (`int(n * 0.6)`,
`int(n * 0.8)`), so the same days give the same boundaries.

A trade belongs to the split of the day it *opens* on. Which days are split is
the caller's choice: every day in the data, or a filtered set, as v28 does
with the days that have a usable Asia range.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import Enum

import pandas as pd

__all__ = ["Split", "assign_splits", "split_dates"]


class Split(Enum):
    DISCOVERY = "discovery"
    VALIDATION = "validation"
    TEST = "test"


def split_dates(
    dates: Iterable[date],
    *,
    discovery: float = 0.60,
    validation: float = 0.20,
) -> dict[date, Split]:
    """Map each distinct date to its split. The test split gets what's left."""
    if discovery <= 0 or validation <= 0 or discovery + validation >= 1:
        raise ValueError(
            f"need discovery > 0, validation > 0 and room left for test, "
            f"got discovery={discovery}, validation={validation}"
        )

    ordered = sorted(set(dates))
    n = len(ordered)
    discovery_end = int(n * discovery)
    validation_end = int(n * (discovery + validation))

    return {
        day: Split.DISCOVERY if i < discovery_end else Split.VALIDATION if i < validation_end else Split.TEST
        for i, day in enumerate(ordered)
    }


def assign_splits(open_dts: pd.Series, by_date: dict[date, Split]) -> pd.Series:
    """The split name (`Split.value`) of each trade, from the date it opens on.

    A trade on a date `by_date` doesn't cover raises: quietly leaving it out
    would make the per-split numbers disagree with the totals.
    """
    days = open_dts.dt.date
    uncovered = sorted(set(days) - by_date.keys())
    if uncovered:
        raise ValueError(f"{len(uncovered)} trade date(s) not covered by the split, first {uncovered[0]}")

    return days.map(lambda day: by_date[day].value).astype("str")
