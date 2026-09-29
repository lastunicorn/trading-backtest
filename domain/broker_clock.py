"""The MT5 broker-server clock: New York wall time + 7 hours.

    from domain.broker_clock import BROKER_SERVER_TZ, timezone_by_name

    datetime(2020, 1, 6, 0, 0, tzinfo=BROKER_SERVER_TZ).astimezone(UTC)   # 2020-01-05 22:00 UTC
    timezone_by_name("broker") is BROKER_SERVER_TZ                        # what CLI flags accept
    timezone_by_name("Europe/London")                                     # any IANA name too
    timezone_name(BROKER_SERVER_TZ)                                       # "broker" -- and back again

The broker's server runs on the common "New York close" clock. FX opens Sunday
17:00 New York, which is Monday 00:00 on the server, so every trading week in
the exports runs Monday 00:00 -> Friday 23:55. That makes it GMT+2 in winter
and GMT+3 in summer, switching on the **US** daylight-saving dates. The data
confirms it: in all 24 weeks of 2020-2026 where the US and EU switch dates
disagree, the week still opens Monday 00:00. So it is not `Europe/Athens`,
which switches on the EU dates and would be an hour off in those weeks.

No IANA zone is exactly "New York + 7h", so `ShiftedZone` builds one: a real
zone's wall clock plus a fixed shift. It is a proper `tzinfo`, so stdlib
`datetime.astimezone` handles it. pandas does not accept custom `tzinfo`
classes; `domain.pandas_approach.shift_timezone` converts through `base`
instead.

Stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

__all__ = ["BROKER_SERVER_TZ", "BROKER_TZ_NAME", "ShiftedZone", "timezone_by_name", "timezone_name"]


class ShiftedZone(tzinfo):
    """`base`'s wall clock moved by `shift`: `base` reads 17:00 when this reads 17:00 + shift.

    Offsets, DST and ambiguous/non-existent hours all follow `base`, moved
    by `shift`.
    """

    def __init__(self, base: ZoneInfo, shift: timedelta, name: str) -> None:
        self.base = base
        self.shift = shift
        self.name = name

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        if dt is None:
            return None
        return self.base.utcoffset(self._base_wall(dt)) + self.shift

    def dst(self, dt: datetime | None) -> timedelta | None:
        if dt is None:
            return None
        return self.base.dst(self._base_wall(dt))

    def tzname(self, dt: datetime | None) -> str:
        return self.name

    def fromutc(self, dt: datetime) -> datetime:
        in_base = dt.replace(tzinfo=timezone.utc).astimezone(self.base)
        return (in_base.replace(tzinfo=None) + self.shift).replace(tzinfo=self, fold=in_base.fold)

    def __getinitargs__(self) -> tuple:
        """What `tzinfo.__reduce__` rebuilds this from, so copy and pickle work (a dataclass's `asdict` deep-copies)."""
        return self.base, self.shift, self.name

    def _base_wall(self, dt: datetime) -> datetime:
        """The `base` wall-clock reading at the same instant as `dt` on this clock."""
        return (dt.replace(tzinfo=None) - self.shift).replace(fold=dt.fold)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ShiftedZone):
            return NotImplemented
        return (self.base, self.shift) == (other.base, other.shift)

    def __hash__(self) -> int:
        return hash((self.base, self.shift))

    def __repr__(self) -> str:
        return f"ShiftedZone({self.base.key!r}, {self.shift!r}, {self.name!r})"

    def __str__(self) -> str:
        return self.name


BROKER_SERVER_TZ = ShiftedZone(ZoneInfo("America/New_York"), timedelta(hours=7), "broker-server (America/New_York+7h)")

# The name CLI timezone flags accept for BROKER_SERVER_TZ.
BROKER_TZ_NAME = "broker"


def timezone_by_name(name: str) -> tzinfo:
    """`BROKER_SERVER_TZ` for "broker" (any case), otherwise the IANA zone `name`.

    Raises `zoneinfo.ZoneInfoNotFoundError` for an unknown name, as `ZoneInfo` does.
    """
    if name.strip().lower() == BROKER_TZ_NAME:
        return BROKER_SERVER_TZ
    return ZoneInfo(name)


def timezone_name(zone: tzinfo) -> str:
    """The name `timezone_by_name` reads back as `zone`: "broker", or an IANA key.

    Any other tzinfo (a fixed `datetime.timezone` offset) has no such name; its
    `str()` is returned, for display.
    """
    if zone == BROKER_SERVER_TZ:
        return BROKER_TZ_NAME
    if isinstance(zone, ZoneInfo):
        return zone.key
    return str(zone)
