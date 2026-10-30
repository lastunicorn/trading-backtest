"""How a backtest's trades are grouped for reporting: `SplitMode`.

    from domain.pandas_approach.splits import SplitMode, assign_splits, split_labels

    by_date = split_labels(data.data["datetime"].dt.date, SplitMode.MONTHLY)  # {date: "2024-03"}
    trades["split"] = assign_splits(trades["open_dt"], by_date)

`dvt` is the chronological discovery / validation / test split; `monthly`
and `yearly` label each day with its calendar month ("2024-03") or year
("2024"). A new grouping is one `SplitMode` member plus one branch in
`split_labels`.

For `dvt`, the research methodology's invariant: calendar days are sorted and sliced
60 / 20 / 20, never shuffled, and a result only counts when it holds in all
three. The boundaries are `int(n * 0.6)` and `int(n * 0.8)`, so the same
days always give the same boundaries.

A trade belongs to the split of the day it *opens* on. Which days are split is
the caller's choice: every day in the data, or a filtered set, as
`NarrowAsiaFade` does with the days that have a usable Asia range.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from enum import Enum

import pandas as pd

__all__ = ["Split", "SplitMode", "assign_splits", "split_dates", "split_labels"]


class SplitMode(Enum):
    NONE = "none"
    DVT = "dvt"
    MONTHLY = "monthly"
    YEARLY = "yearly"


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


def split_labels(dates: Iterable[date], mode: SplitMode) -> dict[date, str]:
    """Map each distinct date to the name of its split, in chronological order.

    So `list(dict.fromkeys(labels.values()))` is the split names in order:
    discovery, validation, test for `dvt`; oldest period first otherwise.
    """
    ordered = sorted(set(dates))
    if mode is SplitMode.DVT:
        by_date = split_dates(ordered)
        return {day: by_date[day].value for day in ordered}
    if mode is SplitMode.MONTHLY:
        return {day: f"{day:%Y-%m}" for day in ordered}
    if mode is SplitMode.YEARLY:
        return {day: str(day.year) for day in ordered}
    raise ValueError(f"no split labels for {mode}")


def assign_splits(open_dts: pd.Series, by_date: dict[date, str]) -> pd.Series:
    """The split name of each trade, from the date it opens on.

    A trade on a date `by_date` doesn't cover raises: quietly leaving it out
    would make the per-split numbers disagree with the totals.
    """
    days = open_dts.dt.date
    uncovered = sorted(set(days) - by_date.keys())
    if uncovered:
        raise ValueError(f"{len(uncovered)} trade date(s) not covered by the split, first {uncovered[0]}")

    return days.map(by_date).astype("str")
