from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as _date, datetime

from domain.bar import Bar


@dataclass
class DailySessionBase(ABC):
    """One calendar day's session lifecycle: accumulates bars via add_bar()
    until this session's own window_end (force-closing itself the moment a
    bar reaches it), tracks first/last candle seen, and freezes once closed
    -- add_bar() or close() again afterwards raises. What actually happens
    to a bar before window_end, and what "close whatever's open" means, is
    delegated to the concrete subclass via _process_bar/_close_positions."""

    day: _date

    # Subclass __post_init__ must set this before any add_bar() call.
    start_dt: datetime = field(init=False, repr=False)
    end_dt: datetime = field(init=False, repr=False)

    _is_closed: bool = field(default=False, init=False, repr=False)
    _closed_dt: datetime | None = field(default=None, init=False, repr=False)

    _first_candle_dt: datetime | None = field(default=None, init=False, repr=False)
    _last_candle_dt: datetime | None = field(default=None, init=False, repr=False)

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def closed_dt(self) -> datetime | None:
        return self._closed_dt

    @property
    def first_candle_dt(self) -> datetime | None:
        return self._first_candle_dt

    @property
    def last_candle_dt(self) -> datetime | None:
        return self._last_candle_dt

    def add_bar(self, bar: Bar) -> bool:
        if self._is_closed:
            raise RuntimeError(f"DailySession for {self.day} is already closed at {self.closed_dt}. Cannot add more bars.")

        if bar.dt < self.start_dt:
            return False

        if bar.dt >= self.end_dt:
            self.close_at_session_end()
            return False

        if self._first_candle_dt is None:
            self._first_candle_dt = bar.dt

        if self._last_candle_dt is not None and bar.dt <= self._last_candle_dt:
            return False

        self._last_candle_dt = bar.dt

        continue_processing: bool = self._on_before_process_positions(bar)

        if continue_processing:
            self._process_positions(bar)

        return True

    def close_at_session_end(self) -> bool:
        return self.close_at(self.end_dt)

    def close_at(self, at: datetime) -> bool:
        if self._is_closed:
            if at != self.closed_dt:
                raise RuntimeError(f"DailySession for {self.day} is already closed at {self.closed_dt}")
            return False

        self._close_all_positions(at)

        self._is_closed = True
        self._closed_dt = at

        return True

    @abstractmethod
    def _on_before_process_positions(self, bar: Bar) -> bool:
        """Called before processing positions for the given bar. Return whether to continue processing."""

    @abstractmethod
    def _process_positions(self, bar: Bar) -> None:
        """Process both pending and active positions for the given bar."""

    @abstractmethod
    def _close_all_positions(self, at: datetime) -> None:
        """Close out anything still open, at `at`. Called by close() only
        after the idempotency check passes."""
