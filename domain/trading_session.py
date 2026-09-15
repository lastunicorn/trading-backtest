from dataclasses import dataclass, field
from datetime import UTC, datetime

from domain.bar import Bar
from domain.bar_block import BarBlock


@dataclass
class TradingSession:

    start_dt: datetime
    end_dt: datetime

    _bar_block: BarBlock = field(default_factory=BarBlock, init=False, repr=False)

    @property
    def bars(self) -> BarBlock:
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
        """`start_dt` converted to UTC."""
        if self.start_dt.tzinfo is None:
            return self.start_dt.replace(tzinfo=UTC)
        return self.start_dt.astimezone(UTC)

    def end_dt_utc(self) -> datetime:
        """`end_dt` converted to UTC."""
        if self.end_dt.tzinfo is None:
            return self.end_dt.replace(tzinfo=UTC)
        return self.end_dt.astimezone(UTC)

    def contains(self, dt: datetime) -> bool:
        """Whether `dt` falls inside the Trading session window.

        A naive `dt` is assumed to already be in the same timezone as `start_dt` and `end_dt`.
        An aware `dt` is converted to UTC for comparison.
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        dt_utc = dt.astimezone(UTC)

        return self.start_dt_utc() <= dt_utc < self.end_dt_utc()

    def add(self, bar: Bar) -> None:
        """Add a bar to the underlying `BarBlock`."""
        if not self.contains(bar.dt):
            return

        self._bar_block.add(bar)