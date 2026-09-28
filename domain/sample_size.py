"""`SampleSize`: an amount plus a unit, parsed from a compact string.

Stdlib only. The unit letters are case-sensitive so "m" (minute) and "M"
(month) don't collide -- see `SampleUnit`.

    from domain.sample_size import SampleSize, SampleUnit

    spec = SampleSize.Parse("4h")
    spec.amount, spec.unit             # 4, SampleUnit.Hour
    spec.to_pandas_rule()              # "4h"
    str(spec)                          # "4h" -- round-trips through Parse
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = ["SampleSize", "SampleUnit"]


class SampleUnit(Enum):
    """One unit letter from an interval string. Values are the letters themselves."""

    Minute = "m"
    Hour = "h"
    Day = "d"
    Week = "w"
    Month = "M"


# Derived from SampleUnit rather than duplicated, so a unit can't be added to
# one and forgotten in the other.
_UNIT_LETTERS = "".join(unit.value for unit in SampleUnit)
_INTERVAL_RE = re.compile(rf"(\d+)([{_UNIT_LETTERS}])")

# SampleUnit -> the pandas frequency alias it means. Months map to "MS"
# (month start) so a monthly bucket is labelled by its first day, like every
# other bucket here is labelled by its start.
_PANDAS_ALIAS = {
    SampleUnit.Minute: "min",
    SampleUnit.Hour: "h",
    SampleUnit.Day: "D",
    SampleUnit.Week: "W",
    SampleUnit.Month: "MS",
}


@dataclass(frozen=True, slots=True)
class SampleSize:
    """An interval width: an amount plus a unit, e.g. amount=5, unit=Minute for "5m"."""

    amount: int
    unit: SampleUnit

    @staticmethod
    def Parse(interval: str) -> SampleSize:
        """Parse a compact interval string ("5m", "4h", "7d", "2w", "3M").

        Case-sensitive: "m" is minutes, "M" is months. Raises ValueError on
        anything else, or on a non-positive amount.
        """
        match = _INTERVAL_RE.fullmatch(interval)

        if match is None:
            raise ValueError(
                f"invalid interval {interval!r}; expected an integer amount "
                f"plus a unit letter ({'/'.join(_UNIT_LETTERS)}, case-sensitive), "
                "e.g. '5m', '4h', '7d', '2w', '3M'"
            )

        amount = int(match.group(1))

        if amount <= 0:
            raise ValueError(f"interval amount must be positive, got {interval!r}")

        return SampleSize(amount, SampleUnit(match.group(2)))

    def __str__(self) -> str:
        """The compact form `Parse` reads: amount then unit letter ("5m", "3M")."""
        return f"{self.amount}{self.unit.value}"

    def to_pandas_rule(self) -> str:
        """The pandas resample rule this size means ("5m" -> "5min", "3M" -> "3MS")."""
        return f"{self.amount}{_PANDAS_ALIAS[self.unit]}"
