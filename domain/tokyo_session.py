"""`TokyoSession`: a `BarBlock` scoped to the Tokyo session's daily time window.

Domain vocabulary alongside `bar_block.BarBlock` -- a `TokyoSession` accumulates
bars exactly like any `BarBlock`, but additionally knows the window (00:00-09:00,
end exclusive) that makes a bar "one of its own": `contains()` answers that for
any `datetime` without the caller re-stating the window bounds.

Stdlib only, and imports only `bar_block.BarBlock` from `domain/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as _time

from domain.bar_block import BarBlock

__all__ = ["TokyoSession"]


@dataclass
class TokyoSession(BarBlock):
    """A `BarBlock` for the Tokyo session. Empty until the first `add()`, same as `BarBlock`."""

    TOKYO_START = _time(0, 0)
    TOKYO_END = _time(9, 0)  # exclusive

    def contains(self, dt: datetime) -> bool:
        """Whether `dt`'s time-of-day falls inside the Tokyo window."""
        return self.TOKYO_START <= dt.time() < self.TOKYO_END
