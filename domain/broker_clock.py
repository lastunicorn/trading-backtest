"""The source clocks no IANA zone matches: the MT5 broker server's and histdata.com's.

    from domain.broker_clock import BROKER_SERVER_TZ, HISTDATA_TZ, timezone_by_name

    datetime(2020, 1, 6, 0, 0, tzinfo=BROKER_SERVER_TZ).astimezone(UTC)   # 2020-01-05 22:00 UTC
    timezone_by_name("broker") is BROKER_SERVER_TZ                        # what CLI flags accept
    timezone_by_name("histdata") is HISTDATA_TZ
    timezone_by_name("Europe/London")                                     # any IANA name too
    timezone_name(BROKER_SERVER_TZ)                                       # "broker" -- and back again

The broker's server runs on the common "New York close" clock. FX opens Sunday
17:00 New York, which is Monday 00:00 on the server, so every trading week in
the exports runs Monday 00:00 -> Friday 23:55. That makes it GMT+2 in winter
and GMT+3 in summer, switching on the **US** daylight-saving dates. The data
confirms it: in all 24 weeks of 2020-2026 where the US and EU switch dates
disagree, the week still opens Monday 00:00. So it is not `Europe/Athens`,
which switches on the EU dates and would be an hour off in those weeks.

histdata.com's MetaTrader downloads are on New York's clock with the **EU**
daylight-saving dates: UTC-5 in winter and UTC-4 in summer, like New York, but
in the weeks the US and EU switch dates disagree (US already on, or still on,
summer time; EU on winter time) they stay at UTC-5, an hour behind New York.
That is London's clock minus 5 hours. The data shows it: those weeks open
Sunday 16:00 instead of 17:00, and their closes match the broker exports at
+8h instead of +7h. That holds from 2019 on. The 2016-2018 downloads are
plain New York time (their mismatch weeks open Sunday 17:00 and close Friday
16:59), and the change happened between Nov 2018 and Mar 2019, a stretch with
no mismatch week to tell the two apart. So `HISTDATA_TZ` is New York before
2019-01-01 and London - 5h from then on.

No IANA zone is exactly "New York + 7h" or "London - 5h", so `ShiftedZone`
builds them: a real zone's wall clock plus a fixed shift. `SwitchingZone`
joins two zones at a moment, for a source that changed its clock. Both are
proper `tzinfo`s, so stdlib `datetime.astimezone` handles them. pandas does
not accept custom `tzinfo` classes; `domain.pandas_approach.shift_timezone`
converts through the real zones underneath instead.

Stdlib only.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

__all__ = [
    "BROKER_SERVER_TZ", "BROKER_TZ_NAME", "HISTDATA_TZ", "HISTDATA_TZ_NAME", "ShiftedZone", "SwitchingZone",
    "is_utc", "timezone_by_name", "timezone_name",
]


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


class SwitchingZone(tzinfo):
    """`before`'s rules until the wall-clock moment `switch`, `after`'s from it on.

    `before` and `after` must agree on the UTC offset at `switch`, so the
    switch moves no clock and every wall-clock reading near it means one
    instant. `ValueError` otherwise.
    """

    def __init__(self, before: tzinfo, after: tzinfo, switch: datetime, name: str) -> None:
        if before.utcoffset(switch) != after.utcoffset(switch):
            raise ValueError(f"{before} and {after} have different UTC offsets at {switch}: the switch would move the clock")
        self.before = before
        self.after = after
        self.switch = switch
        self.name = name

    def zone_at(self, dt: datetime) -> tzinfo:
        """`before` or `after`: the zone whose rules hold at the wall-clock reading `dt`."""
        return self.before if dt.replace(tzinfo=None) < self.switch else self.after

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        if dt is None:
            return None
        return self.zone_at(dt).utcoffset(dt)

    def dst(self, dt: datetime | None) -> timedelta | None:
        if dt is None:
            return None
        return self.zone_at(dt).dst(dt)

    def tzname(self, dt: datetime | None) -> str:
        return self.name

    def fromutc(self, dt: datetime) -> datetime:
        instant = dt.replace(tzinfo=timezone.utc)
        local = instant.astimezone(self.after)
        if local.replace(tzinfo=None) < self.switch:
            local = instant.astimezone(self.before)
        return local.replace(tzinfo=self)

    def __getinitargs__(self) -> tuple:
        """What `tzinfo.__reduce__` rebuilds this from, so copy and pickle work."""
        return self.before, self.after, self.switch, self.name

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SwitchingZone):
            return NotImplemented
        return (self.before, self.after, self.switch) == (other.before, other.after, other.switch)

    def __hash__(self) -> int:
        return hash((self.before, self.after, self.switch))

    def __repr__(self) -> str:
        return f"SwitchingZone({self.before!r}, {self.after!r}, {self.switch!r}, {self.name!r})"

    def __str__(self) -> str:
        return self.name


BROKER_SERVER_TZ = ShiftedZone(ZoneInfo("America/New_York"), timedelta(hours=7), "broker-server (America/New_York+7h)")

# histdata's clock: New York's until 2019, then London's - 5h (New York's on the EU daylight-saving dates).
HISTDATA_TZ = SwitchingZone(
    ZoneInfo("America/New_York"),
    ShiftedZone(ZoneInfo("Europe/London"), timedelta(hours=-5), "Europe/London-5h"),
    datetime(2019, 1, 1),
    "histdata (America/New_York, from 2019 Europe/London-5h)",
)

# The names CLI timezone flags (and backtest configs) accept for the zones above.
BROKER_TZ_NAME = "broker"
HISTDATA_TZ_NAME = "histdata"

_NAMED_ZONES: dict[str, tzinfo] = {BROKER_TZ_NAME: BROKER_SERVER_TZ, HISTDATA_TZ_NAME: HISTDATA_TZ}


def timezone_by_name(name: str) -> tzinfo:
    """`BROKER_SERVER_TZ` for "broker", `HISTDATA_TZ` for "histdata" (any case), otherwise the IANA zone `name`.

    Raises `zoneinfo.ZoneInfoNotFoundError` for an unknown name, as `ZoneInfo` does.
    """
    named = _NAMED_ZONES.get(name.strip().lower())
    return named if named is not None else ZoneInfo(name)


def timezone_name(zone: tzinfo) -> str:
    """The name `timezone_by_name` reads back as `zone`: "broker", "histdata", or an IANA key.

    Any other tzinfo (a fixed `datetime.timezone` offset) has no such name; its
    `str()` is returned, for display.
    """
    for name, named in _NAMED_ZONES.items():
        if zone == named:
            return name
    if isinstance(zone, ZoneInfo):
        return zone.key
    return str(zone)


def is_utc(zone: tzinfo) -> bool:
    """Whether `zone` is UTC all year (checked in winter and summer, so a DST zone fails)."""
    return all(datetime(2020, month, 1, tzinfo=zone).utcoffset() == timedelta(0) for month in (1, 7))
