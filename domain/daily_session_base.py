from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date as _date, datetime

from domain.bar import Bar
from domain.position import PendingPosition, Position


@dataclass
class DailySessionBase(ABC):
    """One calendar day's session lifecycle: accumulates bars via add_bar()
    until this session's own end_dt (force-closing itself the moment a bar
    reaches it), tracks first/last candle seen, and freezes once closed --
    add_bar() or close_at() again afterwards raises. What actually happens
    to a bar before end_dt is delegated to the concrete subclass via
    _process_bar; what "close whatever's open" means is delegated via
    _close_all_positions.

    _process_bar is itself free to reuse the pending/active-position
    machinery below (_process_positions, and the _process_pending_positions/
    _process_active_positions it composes) rather than reimplementing it --
    a subclass only needs to keep `_pending_positions`/`_positions`
    populated. DailySession does this; a future subclass with no reference-
    session-resolution step of its own could call _process_positions(bar)
    directly as its entire _process_bar."""

    day: _date

    # Subclass __post_init__ must set this before any add_bar() call.
    start_dt: datetime = field(init=False, repr=False)
    end_dt: datetime = field(init=False, repr=False)

    _is_closed: bool = field(default=False, init=False, repr=False)
    _closed_dt: datetime | None = field(default=None, init=False, repr=False)

    _first_candle_dt: datetime | None = field(default=None, init=False, repr=False)
    _last_candle_dt: datetime | None = field(default=None, init=False, repr=False)

    _pending_positions: list[PendingPosition] = field(default_factory=list, init=False, repr=False)
    _positions: list[Position] = field(default_factory=list, init=False, repr=False)

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

        self._process_bar(bar)

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
    def _process_bar(self, bar: Bar) -> None:
        """Handle one bar that arrived before end_dt -- e.g. whether it
        should still feed a reference session, and/or whether it's within
        the window pending/active positions are processed for. The default
        body below is a ready-made implementation a subclass can delegate
        to (directly, or via super()._process_bar(bar)) once it has decided
        the bar should be processed."""
        self._process_positions(bar)

    def _process_positions(self, bar: Bar) -> None:
        """Try to open every still-pending position against `bar`, then
        update every still-open position against it -- in that order, so a
        position opened by this same bar is immediately checked against it
        too (matches the old same-bar-hit behavior from before pending/
        active positions were split into separate lists)."""
        self._process_pending_positions(bar)
        self._process_active_positions(bar)

    def _process_pending_positions(self, bar):
        """Iterates a snapshot (`list(...)`), not `self._pending_positions`
        directly -- removing from the list being iterated skips whatever
        shifts into the removed slot, silently dropping a same-bar trigger
        whenever more than one pending position hits on the same bar."""
        pending_positions = list(self._pending_positions)

        for pending_positon in pending_positions:
            if pending_positon is not None:
                new_position = pending_positon.try_open_position(bar)

                if new_position is not None:
                    self._pending_positions.remove(pending_positon)
                    self._positions.append(new_position)

    def _process_active_positions(self, bar):
        for position in self._positions:
            if position is not None and not position.is_closed:
                position.hit(bar)

    @abstractmethod
    def _close_all_positions(self, at: datetime) -> None:
        """Close out anything still open, at `at`. Called by close_at() only
        after the idempotency check passes."""
