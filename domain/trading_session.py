from domain.bar_block import BarBlock


from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass
class TradingSession:

    _bar_block: BarBlock = BarBlock()

    start_dt: datetime
    end_dt: datetime

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

    def add(self, bar) -> None:
        """Add a bar to the underlying `BarBlock`."""
        if not self.contains(bar.datetime):
            return

        self._bar_block.add(bar)