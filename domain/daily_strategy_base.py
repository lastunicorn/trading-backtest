from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date as _date

from domain.bar import Bar
from domain.daily_session_base import DailySessionBase


@dataclass
class DailyStrategyBase(ABC):
    """Feeds one chronological bar at a time via add_bar(); creates a new
    DailySessionBase the moment a bar for a new calendar day appears
    (session creation itself is delegated to _create_session, since only
    the concrete strategy knows how to build its own session type), keeps
    every day's session (_sessions/_session_order) plus the still-live ones
    (_live_sessions), and notifies on_session_closed exactly once per
    session the moment it closes -- whether via a bar in add_bar() crossing
    its end_dt, or a force-close in close_live_sessions() once the bar
    stream truly ends.

    Fed the entire bar stream from first bar to last by a single instance --
    it doesn't split, chunk, or hand off state to another instance."""

    on_session_closed: Callable[[DailySessionBase], None] | None = None

    _sessions: dict[_date, DailySessionBase] = field(default_factory=dict, init=False, repr=False)
    _session_order: list[_date] = field(default_factory=list, init=False, repr=False)
    _live_sessions: list[DailySessionBase] = field(default_factory=list, init=False, repr=False)

    def add_bar(self, bar: Bar) -> None:
        """Feed one bar (bars must arrive chronologically). Creates a new
        session the moment a bar for a new calendar day appears. Every
        currently-live session then receives the bar, so a day's own
        session and a still-resolving earlier day's session are both fed
        the same bar. A session force-closes itself, and freezes, once a
        bar reaches its end_dt; add_bar() only has to notice that and
        drop it from the live list."""
        bar_date = bar.dt.date()

        if bar_date not in self._sessions:
            session = self._create_session(bar_date)
            self._sessions[bar_date] = session
            self._session_order.append(bar_date)
            self._live_sessions.append(session)

        for session in list(self._live_sessions):
            session.add_bar(bar)

            if session.is_closed:
                self._live_sessions.remove(session)
                self._notify_closed(session)

    def close_live_sessions(self) -> None:
        """Force-close every still-live session at its own end_dt."""
        for session in self._live_sessions:
            session.close_at(session.end_dt)
            self._notify_closed(session)
        self._live_sessions.clear()

    def _notify_closed(self, session: DailySessionBase) -> None:
        if self.on_session_closed is not None:
            self.on_session_closed(session)

    @abstractmethod
    def _create_session(self, day: _date) -> DailySessionBase:
        """Build a new, unfed session for `day`. Called once per new
        calendar day seen by add_bar(); must not itself call add_bar()."""
