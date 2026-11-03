"""The errors this library raises."""

from __future__ import annotations

import os

__all__ = ["AmbiguousLayoutError", "MetatraderParseError"]


class MetatraderParseError(ValueError):
    """A line of an export that could not be parsed, raised when reading strictly."""

    def __init__(self, path: str, line_no: int, reason: str, line: str = ""):
        self.path = path
        self.line_no = line_no
        self.reason = reason
        self.line = line

        location = f"{os.path.basename(path)}:{line_no}"
        detail = f"  |  {line.strip()[:80]}" if line else ""
        super().__init__(f"{location}: {reason}{detail}")


class AmbiguousLayoutError(ValueError):
    """A headerless export whose column count doesn't say which field each column is."""
