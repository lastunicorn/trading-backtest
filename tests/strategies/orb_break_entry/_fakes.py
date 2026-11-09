"""Synthetic days for the `strategies.orb_break_entry` tests.

The days are `tests.strategies.opening_range._fakes`'s: a 1.0995-1.1005 range
at 09:30-09:45 ET, quiet bars strictly inside it. Its midpoint 1.1000 is the
stop, so a 5-pip risk and a 2R target 10 pips beyond the entry.
"""

from tests.strategies.opening_range._fakes import (FLAT, MISMATCH_TUESDAY, QUIET, SUMMER_TUESDAY, TUESDAY,
                                                    WEDNESDAY, data, day_frame, range_at)

__all__ = ["BOTH_WAYS", "BREAK_DOWN", "BREAK_UP", "FLAT", "MISMATCH_TUESDAY", "QUIET", "SUMMER_TUESDAY",
           "TUESDAY", "WEDNESDAY", "data", "day_frame", "range_at"]

BREAK_UP = (1.1003, 1.1008, 1.1002, 1.1007)
BREAK_DOWN = (1.0997, 1.0998, 1.0992, 1.0993)
BOTH_WAYS = (1.1000, 1.1008, 1.0992, 1.1000)
