"""`TokyoSession`: a `BarBlock` scoped to the Tokyo session's daily time window.

Domain vocabulary alongside `bar_block.BarBlock` -- a `TokyoSession` accumulates
bars exactly like any `BarBlock`, but additionally knows the window (00:00-09:00,
end exclusive) that makes a bar "one of its own": `contains()` answers that for
any `datetime` without the caller re-stating the window bounds.

Stdlib only, and imports only `bar_block.BarBlock` from `domain/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time, tzinfo

from domain.bar_block import BarBlock

__all__ = ["TokyoSession"]


@dataclass
class TokyoSession(BarBlock):
    """A `BarBlock` for the Tokyo session. Empty until the first `add()`, same as `BarBlock`."""

    TOKYO_START = time(0, 0)
    TOKYO_END = time(6, 30)  # exclusive

    timezone: tzinfo = UTC

    @property
    def start_time(self) -> time:
        """`TOKYO_START`, carrying `timezone`."""
        return self.TOKYO_START.replace(tzinfo=self.timezone)

    @property
    def end_time(self) -> time:
        """`TOKYO_END`, carrying `timezone`."""
        return self.TOKYO_END.replace(tzinfo=self.timezone)

    def contains(self, dt: datetime) -> bool:
        """Whether `dt`'s time-of-day falls inside the Tokyo window.

        A naive `dt` is assumed to already be in `timezone`'s wall clock, same
        as always. An aware `dt` is converted to `timezone` first -- `.time()`
        would otherwise silently strip its `tzinfo` without converting.
        """
        if dt.tzinfo is not None:
            dt = dt.astimezone(self.timezone).replace(tzinfo=None)
        return self.TOKYO_START <= dt.time() < self.TOKYO_END

