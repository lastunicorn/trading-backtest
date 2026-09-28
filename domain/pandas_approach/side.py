"""`Side`: which way a position faces.

    from domain.pandas_approach.side import Side

    Side.LONG.value     # "long"

Its own module rather than living in `position.py` so strategies, the
simulator and the RSI divergence helpers can all share it without importing
each other.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["Side"]


class Side(Enum):
    LONG = "long"
    SHORT = "short"
