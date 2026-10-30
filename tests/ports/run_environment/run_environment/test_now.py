"""Tests for `ports.run_environment.now`."""

from datetime import datetime

from ports.run_environment import now


def test_is_the_current_naive_local_time() -> None:
    before = datetime.now()
    current = now()
    after = datetime.now()

    assert current.tzinfo is None
    assert before <= current <= after
