"""`SampleSize`: an amount plus a unit, parsed from a compact string.

Stdlib only. The unit letters are case-sensitive so "m" (minute) and "M"
(month) don't collide -- see `SampleUnit`.

    from domain.sample_size import SampleSize, SampleUnit

    spec = SampleSize.Parse("4h")
    spec.amount, spec.unit             # 4, SampleUnit.Hour
    spec.to_pandas_rule()              # "4h"
    str(spec)                          # "4h" -- round-trips through Parse
    spec.can_be_resampled_from(SampleSize.Parse("15m"))   # True: 4h is a whole number of 15m bars
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

# SampleUnit -> its width in minutes, for the fixed-width units. Months have
# no fixed width, so they are handled apart in `can_be_resampled_from`.
_MINUTES = {
    SampleUnit.Minute: 1,
    SampleUnit.Hour: 60,
    SampleUnit.Day: 24 * 60,
    SampleUnit.Week: 7 * 24 * 60,
}

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

    def can_be_resampled_from(self, source: SampleSize) -> bool:
        """Whether bars of size `source` can be merged into bars of this size.

        Resampling only coarsens, and only cleanly: each bar here must be a
        whole number of `source` bars ("15m" from "5m" yes, "7m" from "5m"
        no, "1m" from "5m" no). A month holds a whole number of any size that
        divides a day, and of a smaller number of months.
        """
        if self.unit is SampleUnit.Month:
            if source.unit is SampleUnit.Month:
                return self.amount % source.amount == 0
            return _MINUTES[SampleUnit.Day] % source._minutes() == 0
        if source.unit is SampleUnit.Month:
            return False
        return self._minutes() % source._minutes() == 0

    def _minutes(self) -> int:
        return self.amount * _MINUTES[self.unit]
