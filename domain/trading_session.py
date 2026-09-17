from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.bar_approach.bar import Bar
from domain.bar_approach.bar_block import BarBlock


@dataclass
class TradingSession:

    start_dt: datetime
    end_dt: datetime

    _bar_block: BarBlock = field(default_factory=BarBlock, init=False, repr=False)
    _start_dt_utc: datetime = field(init=False, repr=False)
    _end_dt_utc: datetime = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """`start_dt`/`end_dt` never change after construction, so their UTC
        form is computed once here rather than on every `start_dt_utc()` /
        `end_dt_utc()` / `contains()` call -- the naive conversion is cheap,
        but a `ZoneInfo`-aware one (any DST-observing session template) is not,
        and `contains()` used to redo it on every bar."""
        self._start_dt_utc = self._to_utc(self.start_dt)
        self._end_dt_utc = self._to_utc(self.end_dt)

    @staticmethod
    def _to_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)

    @property
    def bar_block(self) -> BarBlock:
        """The underlying `BarBlock`, for callers that need its full OHLC
        detail (open/close values and timestamps) rather than just the
        aggregate stats exposed directly below."""
        return self._bar_block

    @property
    def range(self) -> float:
        return self._bar_block.range

    @property
    def mid(self) -> float:
        return self._bar_block.mid

    @property
    def high_value(self) -> float:
        return self._bar_block.high_value

    @property
    def low_value(self) -> float:
        return self._bar_block.low_value

    @property
    def bar_count(self) -> int:
        return self._bar_block.bar_count

    def start_dt_utc(self) -> datetime:
        """`start_dt` converted to UTC (cached at construction)."""
        return self._start_dt_utc

    def end_dt_utc(self) -> datetime:
        """`end_dt` converted to UTC (cached at construction)."""
        return self._end_dt_utc

    def contains(self, dt: datetime) -> bool:
        """Whether `dt` falls inside the Trading session window.

        A naive `dt` is assumed to already be in the same timezone as `start_dt` and `end_dt`.
        An aware `dt` is converted to UTC for comparison.
        """
        dt_utc = self._to_utc(dt)
        return self._start_dt_utc <= dt_utc < self._end_dt_utc

    def add(self, bar: Bar) -> bool:
        """Add a bar to the underlying `BarBlock` if it falls inside the
        session window. Returns whether it was added, so a caller that has
        already established the bar's calendar day matches (as
        `TbsDailySession._process_bar_session` does) doesn't need to also
        call `contains()` itself just to learn the same thing `add()` is
        about to check anyway."""
        if not self.contains(bar.dt):
            return False

        self._bar_block.add(bar)
        return True