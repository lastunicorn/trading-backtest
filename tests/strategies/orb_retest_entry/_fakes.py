"""Synthetic days for the `strategies.orb_retest_entry` tests.

The days are `tests.strategies.opening_range._fakes`'s: a 1.0995-1.1005 range
at 09:30-09:45 ET. Its midpoint 1.1000 is the entry, the other side the stop:
a 5-pip risk and a 3R target 15 pips beyond the entry.

The fakes' default quiet bars touch the midpoint, so a day here picks
`quiet_bar`: ABOVE_MID for a long setup, BELOW_MID for a short one. Both stay
strictly inside the range and off the midpoint, so after a break only the bars a
test puts there retest it.
"""

from tests.strategies.opening_range._fakes import (FLAT, MISMATCH_TUESDAY, QUIET, SUMMER_TUESDAY, TUESDAY,
                                                    WEDNESDAY, data, day_frame, range_at)

__all__ = ["ABOVE_MID", "BELOW_MID", "BOTH_WAYS", "BREAK_DOWN", "BREAK_TO_MID", "BREAK_UP", "FLAT",
           "MISMATCH_TUESDAY", "PLUNGE", "QUIET", "RETEST_FROM_ABOVE", "RETEST_FROM_BELOW", "SUMMER_TUESDAY",
           "TUESDAY", "WEDNESDAY", "data", "day_frame", "range_at"]

ABOVE_MID = (1.1002, 1.1004, 1.1001, 1.1003)
BELOW_MID = (1.0998, 1.0999, 1.0996, 1.0997)

BREAK_UP = (1.1003, 1.1008, 1.1002, 1.1007)
BREAK_DOWN = (1.0997, 1.0998, 1.0992, 1.0993)
BOTH_WAYS = (1.1000, 1.1008, 1.0992, 1.1000)
BREAK_TO_MID = (1.1003, 1.1008, 1.0999, 1.1002)      # breaks H and reaches the midpoint in the same bar

RETEST_FROM_ABOVE = (1.1003, 1.1004, 1.0999, 1.1002)   # down to the midpoint, not to L
RETEST_FROM_BELOW = (1.0997, 1.1001, 1.0996, 1.0998)   # up to the midpoint, not to H
PLUNGE = (1.1002, 1.1003, 1.0990, 1.0991)              # through the midpoint and L
