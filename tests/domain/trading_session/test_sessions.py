"""Tests for `domain.trading_session.SESSIONS`, the standard sessions."""

from domain.trading_session import ASIA_SESSION, LONDON_SESSION, NEW_YORK_SESSION, SESSIONS, TOKYO_SESSION


def test_keys_are_the_sessions_names() -> None:
    assert all(name == session.name for name, session in SESSIONS.items())


def test_holds_every_standard_session() -> None:
    assert SESSIONS == {
        "Tokyo": TOKYO_SESSION,
        "Asia": ASIA_SESSION,
        "London": LONDON_SESSION,
        "New York": NEW_YORK_SESSION,
    }
