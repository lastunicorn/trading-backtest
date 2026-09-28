"""Instants for the `domain.broker_clock` tests.

2020 daylight saving: the US switched on Mar 8 and Nov 1, the EU on Mar 29 and
Oct 25. Weeks between those dates are where "New York + 7h" and an EU-schedule
zone like Europe/Athens disagree.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

NEW_YORK = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

WINTER = datetime(2020, 1, 6, 0, 0)       # Monday week open, EST
SUMMER = datetime(2020, 7, 6, 0, 0)       # Monday week open, EDT
MISMATCH = datetime(2020, 3, 16, 0, 0)    # US already on EDT, EU still on standard time
