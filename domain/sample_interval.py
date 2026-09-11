"""`SampleInterval`: an amount plus a unit, parsed from a compact string.

Stdlib only. The unit letters are case-sensitive so "m" (minute) and "M"
(month) don't collide -- see `SampleUnit`.

    from domain.sample_interval import SampleInterval, SampleUnit

    spec = SampleInterval.Parse("4h")
    spec.amount, spec.unit             # 4, SampleUnit.Hour
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

__all__ = ["SampleInterval", "SampleUnit"]


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


@dataclass(frozen=True, slots=True)
class SampleInterval:
    """An interval width: an amount plus a unit, e.g. amount=5, unit=Minute for "5m"."""

    amount: int
    unit: SampleUnit

    @staticmethod
    def Parse(interval: str) -> SampleInterval:
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

        return SampleInterval(amount, SampleUnit(match.group(2)))
